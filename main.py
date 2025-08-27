from scrapers import amazon, lg

model_list = ["OLED55C4", "OLED65C4", "OLED55B4", "OLED65B4"] #, "OLED65C4", "OLED55B4", "OLED65B4"

scrapers = {
    "Amazon": amazon.scrape,
    "LG": lg.scrape,
}

for model in model_list:
    for site, func in scrapers.items():
        try:
            rows = func(model)
            for r in rows:
                print(f"[{site}] {r['model']} - {r['price']} - {r['title']} - {r['url']}")
        except Exception as e:
            print(f"[{site}] {model} failed: {e}")
