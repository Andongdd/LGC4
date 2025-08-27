# utils/report.py
from __future__ import annotations
from datetime import datetime
from pathlib import Path

import re
import math
import pandas as pd

PRICE_RE = re.compile(r"[\d,.]+")

def _to_num(x):
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return None
    if isinstance(x, (int, float)): 
        return float(x)
    m = PRICE_RE.search(str(x))
    return float(m.group(0).replace(",", "")) if m else None

def render_and_save(results: list[dict], outdir: str = "reports") -> pd.DataFrame:
    """
    results: [{'site':..., 'model':..., 'price':..., 'title':..., 'url':...}, ...]
    - 整理为 DataFrame
    - 价格转数字、按 model/site 排序
    - 标注每个 model 的最低价(best=True)
    - 导出 CSV 和自包含 HTML(可直接双击查看)
    - 终端打印一个紧凑表（如果安装了 rich 则彩色高亮）
    """
    if not results:
        print("No results.")
        return pd.DataFrame()

    df = pd.DataFrame(results, columns=["site", "model", "price", "title", "url"])

    # 价格转数值，便于排序/比较
    df["price_num"] = df["price"].map(_to_num)

    # 去掉完全重复的行（同站点同链接）
    df = df.drop_duplicates(subset=["site", "url"], keep="first")

    # 标注每个型号的最低价
    best_idx = df.sort_values("price_num", na_position="last").groupby("model", as_index=False).first().index
    df["best"] = False
    df.loc[best_idx, "best"] = True

    # 排序：型号 -> 价格 -> 站点
    df = df.sort_values(["model", "price_num", "site"], na_position="last").reset_index(drop=True)

    # 输出目录和文件名
    Path(outdir).mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    csv_path = Path(outdir) / f"tv_prices_{stamp}.csv"
    html_path = Path(outdir) / f"tv_prices_{stamp}.html"

    # 导出 CSV
    df.to_csv(csv_path, index=False)

    # 导出 HTML（带最小样式 & 可点击链接 & 最低价高亮）
    styled = (
        df.drop(columns=["price_num"])
          .style
          .apply(lambda s: ["font-weight:700;color:#0b6" if b else "" for b in df["best"]], subset=["price"])
          .format({"url": lambda u: f'<a href="{u}" target="_blank">link</a>'}, na_rep="")
          .hide(axis="index")
    )
    styled.to_html(html_path, doctype_html=True)

    # 终端展示（有 rich 用彩色；没有就普通表）
    try:
        from rich.console import Console
        from rich.table import Table
        from rich import box

        console = Console()
        table = Table(title="TV Price Report", box=box.SIMPLE_HEAVY)
        for col in ["model", "site", "price", "title", "url"]:
            table.add_column(col, overflow="fold")

        for _, r in df.drop(columns=["price_num"]).iterrows():
            price_text = f"[bold green]{r.price}[/]" if r.get("best") else str(r.price)
            table.add_row(str(r.model), str(r.site), price_text, str(r.title), str(r.url))
        console.print(table)
    except Exception:
        # 退化为普通打印
        print(df.drop(columns=["price_num"]).to_string(index=False))

    print(f"\nSaved CSV -> {csv_path}")
    print(f"Saved HTML -> {html_path} (双击即可查看)")
    return df
