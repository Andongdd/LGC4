# utils/notify.py
from __future__ import annotations
import json
from pathlib import Path
from email.message import EmailMessage
from datetime import datetime

import pandas as pd
from config import THRESHOLDS, SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, MAIL_TO, MAIL_FROM

STATE_PATH = Path(".alert_state.json")

def _load_state():
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}

def _save_state(state: dict):
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

def best_prices(df: pd.DataFrame) -> dict:
    """
    按 df['model'] 精确分组（值需为 "OLED55C4" 等四个字符串），返回每个 model 的最低价条目。
    需要列：model, price_num, price, site, url, title
    """
    out = {}
    dfx = df.dropna(subset=["price_num"]).copy()
    if dfx.empty:
        return out
    for model, g in dfx.groupby("model"):
        row = g.sort_values("price_num", ascending=True).iloc[0]
        out[str(model)] = {
            "price_num": float(row["price_num"]),
            "price": str(row.get("price", row["price_num"])),
            "site": str(row.get("site", "")),
            "url": str(row.get("url", "")),
            "title": str(row.get("title", "")),
        }
    return out

def _build_email_subject(triggered: dict) -> str:
    # 例如：Deals: OLED55C4 £989 @ Currys | OLED65B4 £799 @ RS
    parts = []
    for m, info in triggered.items():
        parts.append(f"{m} £{int(info['price_num'])} @ {info['site']}")
    return "Deals: " + " | ".join(parts)

def _build_email_html(triggered: dict) -> str:
    rows = []
    for m, info in triggered.items():
        url = info["url"]
        link = f'<a href="{url}" target="_blank">link</a>' if url else ""
        rows.append(
            f"<tr>"
            f"<td>{m}</td>"
            f"<td>£{info['price_num']:.2f}</td>"
            f"<td>{info['site']}</td>"
            f"<td>{info['title']}</td>"
            f"<td>{link}</td>"
            f"</tr>"
        )
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return f"""
    <html><body>
      <p><b>Price alerts</b> · {ts}</p>
      <table border="1" cellspacing="0" cellpadding="6">
        <thead>
          <tr><th>Model</th><th>Price</th><th>Site</th><th>Title</th><th>URL</th></tr>
        </thead>
        <tbody>{''.join(rows)}</tbody>
      </table>
    </body></html>
    """

def _send_email(subject: str, html: str):
    import smtplib
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = MAIL_FROM
    msg["To"] = ", ".join(MAIL_TO)
    msg.set_content("HTML only.")
    msg.add_alternative(html, subtype="html")

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
        s.starttls()
        s.login(SMTP_USER, SMTP_PASS)
        s.send_message(msg)

def check_and_notify(
    df: pd.DataFrame,
    delta_step: float = 1.0,
    force_send: bool = False,
    verbose: bool = True,
) -> dict:
    """
    - 严格使用 df['model'] 的值（必须是 "OLED55C4"/"OLED65C4"/"OLED55B4"/"OLED65B4"）
    - 与 THRESHOLDS 精确键比较；严格“小于”才触发
    - 去重：同一型号只有当比上次通知价更低 >= delta_step 才再次发；force_send=True 强制发
    """
    # 基础校验
    need_cols = {"model", "price_num"}
    missing = need_cols - set(df.columns)
    if missing:
        if verbose:
            print(f"[ALERT] 缺少列：{missing}，无法比较。")
        return {}

    # 最低价
    current_best = best_prices(df)
    if verbose:
        print("[ALERT] 当前最低价：", {k: v["price_num"] for k, v in current_best.items()})

    state = _load_state()
    triggered = {}

    for model, limit in THRESHOLDS.items():
        info = current_best.get(model)
        if not info:
            if verbose:
                print(f"[ALERT] {model}: 未找到条目（df['model']中没有该值或 price_num 全 NaN）。")
            continue
        p = info["price_num"]
        if pd.isna(p):
            if verbose:
                print(f"[ALERT] {model}: price_num 为 NaN。")
            continue

        if p < float(limit):
            if force_send:
                triggered[model] = info
                if verbose:
                    print(f"[ALERT] {model}: 触发（force_send=True）。")
            else:
                last = state.get(model, {}).get("last_notified_price")
                if last is None or p <= float(last) - float(delta_step):
                    triggered[model] = info
                    if verbose:
                        print(f"[ALERT] {model}: £{p:.2f} < 阈值 £{float(limit):.2f}，且较上次更低（或首次）。")
                else:
                    if verbose:
                        print(f"[ALERT] {model}: 已低于阈值，但未比上次更低（last={last}); 跳过。")
        else:
            if verbose:
                print(f"[ALERT] {model}: 未触发（£{p:.2f} ≥ £{float(limit):.2f}）。")

    if not triggered:
        if verbose:
            print("[ALERT] 本次无触发。")
        return {}

    # 发送邮件
    try:
        subject = _build_email_subject(triggered)
        html = _build_email_html(triggered)
        _send_email(subject, html)
        if verbose:
            print("[ALERT] 邮件已发送。")
    except Exception as e:
        print(f"[ALERT][ERROR] 发送邮件失败：{e}")
        return {}

    # 更新去重状态
    for m, info in triggered.items():
        state[m] = {
            "last_notified_price": info["price_num"],
            "last_site": info["site"],
            "last_url": info["url"],
            "ts": datetime.now().isoformat(timespec="seconds"),
        }
    _save_state(state)
    return triggered
