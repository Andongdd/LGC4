# scrapers/smiths.py

import re
import json
from bs4 import BeautifulSoup

from utils.session import build_session, safe_get

SITE = "Smiths TV"

PRODUCT_URLS = {
    "OLED65C4": "https://www.smithstv.co.uk/lg-oled65c46la-1000007326.html",
    "OLED55C4": "https://www.smithstv.co.uk/lg-oled55c46la-1000007338.html",
}


def extract_sf_layer_price(soup: BeautifulSoup):
    """
    从 <script> 标签中提取 sfDataLayer 结构中的价格。
    """
    pattern = re.compile(r'sfDataLayer\.push\((\{.*?\})\);', re.DOTALL)
    for script in soup.find_all("script"):
        if not script.string:
            continue
        match = pattern.search(script.string)
        if not match:
            continue

        try:
            data = json.loads(match.group(1))
            ecommerce = data.get("ecommerce", {})
            view = ecommerce.get("view", {})
            price = view.get("price")
            if price:
                return str(price)
        except Exception:
            continue

    return None


def scrape(model: str, verify: bool = True):
    """
    返回 SmithsTV 页面中指定型号的价格和库存状态。
    """
    model_key = model.replace(" ", "").upper()
    for key, url in PRODUCT_URLS.items():
        if key in model_key:
            session = build_session()
            html = safe_get(session, url)
            soup = BeautifulSoup(html, "lxml")

            title_el = soup.select_one("title")
            title = title_el.get_text(strip=True) if title_el else key

            price = extract_sf_layer_price(soup)
            in_stock = price is not None

            return [{
                "site": SITE,
                "model": model,
                "title": title,
                "price": f"£{price}" if price else None,
                "in_stock": in_stock,
                "url": url,
            }]

    return []


# 本地调试
if __name__ == "__main__":
    for m in ["LG OLED65C4", "LG OLED55C4"]:
        rows = scrape(m)
        print(f"\n>>> {m}")
        for r in rows:
            print(r)
