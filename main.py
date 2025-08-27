from scrapers import amazon, lg
from utils.report import render_and_save

model_list = ["OLED55C4", "OLED65C4", "OLED55B4", "OLED65B4"] #, "OLED65C4", "OLED55B4", "OLED65B4"

scrapers = {
    "Amazon": amazon.scrape,
    "LG": lg.scrape,
}

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
                    "url": r.get("url"),
                })
        except Exception as e:
            print(f"[{site}] {model} failed: {e}")

# 一次性渲染与导出
render_and_save(all_rows)