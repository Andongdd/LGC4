from __future__ import annotations
import os
import time
import random
import argparse
import logging
import traceback
from datetime import datetime
from pathlib import Path

from filelock import FileLock, Timeout
from dotenv import load_dotenv

from scrapers import amazon, lg, smiths
from utils.report import render_and_save
from utils.notify import check_and_notify

# ---------------- 配置（可被 .env 覆盖） ----------------
DEFAULT_RUN_INTERVAL_MIN = 20          # 运行间隔（分钟）
DEFAULT_RUN_HOUR_START   = 9           # 活跃时段起始整点（含）
DEFAULT_RUN_HOUR_END     = 23          # 活跃时段结束整点（含）
DEFAULT_JITTER_SEC_MIN   = 0           # 每轮执行前的随机抖动（秒）
DEFAULT_JITTER_SEC_MAX   = 120

LOCK_FILE = ".run.lock"                # 防止并发
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# ---------------- 日志 ----------------
logger = logging.getLogger("scheduler")
if not logger.handlers:
    h = logging.StreamHandler()
    h.setFormatter(logging.Formatter("[SCHED] %(message)s"))
    logger.addHandler(h)
logger.setLevel(LOG_LEVEL)

model_list = ["OLED55C4", "OLED65C4", "OLED55B4", "OLED65B4"]

scrapers = {
    "Amazon": amazon.scrape,
    "LG": lg.scrape,
    "Smiths": smiths.scrape,
}

def collect_all_rows() -> list[dict]:
    all_rows = []
    for model in model_list:
        for site, func in scrapers.items():
            try:
                rows = func(model)              # [{'model','price','title','url',...}]
                for r in rows:
                    # 统一字段并补上站点名
                    all_rows.append({
                        "site": site,
                        "model": r.get("model") or model,
                        "price": r.get("price"),
                        "title": r.get("title"),
                        "in_stock": r.get("in_stock"),
                        "url": r.get("url"),
                    })
            except Exception as e:
                print(f"[{site}] {model} failed: {e}")
    return all_rows

def in_active_hours(now: datetime, start_hour: int, end_hour: int) -> bool:
    """本地时间的活跃时段，含起止整点。"""
    return start_hour <= now.hour <= end_hour


def run_cycle_once() -> None:
    """跑一轮：抓取 -> 报告 -> 阈值通知"""
    rows = collect_all_rows()
    if not rows:
        logger.info("本轮未抓到数据（all_rows 为空）。")
    df = render_and_save(rows)                    # 生成 CSV/HTML & 终端表格
    hits = check_and_notify(df, verbose=False)    # 触发则发邮件
    logger.info("Triggered: %s", ", ".join(hits.keys()) if hits else "None")


def safe_run_once(jitter_range=(DEFAULT_JITTER_SEC_MIN, DEFAULT_JITTER_SEC_MAX)) -> None:
    """带文件锁 + 抖动的安全执行，避免重叠运行、高并发访问。"""
    try:
        with FileLock(LOCK_FILE, timeout=1):
            j = random.randint(*jitter_range)
            if j:
                time.sleep(j)
            run_cycle_once()
    except Timeout:
        logger.info("已有实例在运行，跳过本轮。")
    except Exception as e:
        logger.error("本轮异常：%s", e)
        traceback.print_exc()


def loop(interval_min: int, start_hour: int, end_hour: int,
         jitter_min: int, jitter_max: int) -> None:
    """主循环：按间隔在活跃时段运行"""
    logger.info(
        f"启动循环：每 {interval_min} 分钟；活跃 {start_hour}:00–{end_hour}:59；jitter {jitter_min}-{jitter_max}s"
    )
    while True:
        now = datetime.now()
        if in_active_hours(now, start_hour, end_hour):
            safe_run_once((jitter_min, jitter_max))
        else:
            logger.info("非活跃时段，跳过。")
        time.sleep(interval_min * 60)


def main():
    load_dotenv()  # 允许用 .env 覆盖配置（比如 SMTP 密钥、间隔等）

    parser = argparse.ArgumentParser(description="TV price scraper scheduler")
    parser.add_argument("--once", action="store_true", help="只执行一轮并退出")
    parser.add_argument("--loop", action="store_true", help="循环执行（默认）")
    args = parser.parse_args()

    # 读取环境变量覆盖
    interval = int(os.getenv("RUN_INTERVAL_MIN", DEFAULT_RUN_INTERVAL_MIN))
    start_h  = int(os.getenv("RUN_HOUR_START",   DEFAULT_RUN_HOUR_START))
    end_h    = int(os.getenv("RUN_HOUR_END",     DEFAULT_RUN_HOUR_END))
    jit_min  = int(os.getenv("JITTER_SEC_MIN",   DEFAULT_JITTER_SEC_MIN))
    jit_max  = int(os.getenv("JITTER_SEC_MAX",   DEFAULT_JITTER_SEC_MAX))

    if args.once:
        logger.info("单次模式启动。")
        safe_run_once((jit_min, jit_max))
        return

    # 默认进入循环
    logger.info("循环模式启动。按 Ctrl+C 退出。")
    try:
        loop(interval, start_h, end_h, jit_min, jit_max)
    except KeyboardInterrupt:
        logger.info("收到中断，退出。")


if __name__ == "__main__":
    main()
    # rows = collect_all_rows()
    # if not rows:
    #     logger.info("本轮未抓到数据（all_rows 为空）。")
    # df = render_and_save(rows)                    # 生成 CSV/HTML & 终端表格
    # hits = check_and_notify(df, verbose=False) 