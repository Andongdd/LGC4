# scrapers/lg.py

import json
from bs4 import BeautifulSoup

from utils.session import build_session, safe_get

SITE = "LG UK"

# 固定链接列表（你提供的）
PRODUCT_URLS = {
    "OLED65C4": "https://www.lg.com/uk/tvs-soundbars/oled-evo/oled65c46la/",
    "OLED55C4": "https://www.lg.com/uk/tvs-soundbars/oled-evo/oled55c46la/",
    "OLED65B4": "https://www.lg.com/uk/tvs-soundbars/oled/oled65b4ela/",
    "OLED55B4": "https://www.lg.com/uk/tvs-soundbars/oled/oled55b4ela/",
}


def extract_jsonld_price(soup: BeautifulSoup):
    """
    从 JSON-LD 中提取价格和库存状态。
    """
    scripts = soup.find_all("script", {"type": "application/ld+json"})
    for script in scripts:
        try:
            data = json.loads(script.string)
        except Exception:
            continue

        if isinstance(data, list):
            for item in data:
                result = _extract_price(item)
                if result:
                    return result
        else:
            result = _extract_price(data)
            if result:
                return result

    return None, False


def _extract_price(data: dict):
    if data.get("@type") != "product":
        return None

    offer = data.get("offers", {})
    if not isinstance(offer, dict):
        return None

    price = offer.get("price")  # 可能是空字符串
    availability = offer.get("availability", "")
    
    # 判断是否有货
    in_stock = bool(price and price.strip()) and "instock" in availability.lower()

    # 即使 price 是空字符串，也返回
    return price or None, in_stock



def scrape(model: str, verify: bool = True):
    """
    返回 LG UK 固定链接的产品信息（若存在）。
    """
    model_key = model.replace(" ", "").upper()
    for key, url in PRODUCT_URLS.items():
        if key in model_key:
            session = build_session()
            html = safe_get(session, url)
            soup = BeautifulSoup(html, "lxml")

            title_el = soup.select_one("title")
            title = title_el.get_text(strip=True) if title_el else key

            price, in_stock = extract_jsonld_price(soup)
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
    for m in ["LG OLED65C4", "LG OLED55B4"]:
        rows = scrape(m)
        print(f"\n>>> {m}")
        for r in rows:
            print(r)
