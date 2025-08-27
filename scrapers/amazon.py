import re
from urllib.parse import quote
from bs4 import BeautifulSoup
from utils.session import build_session, prefetch_homepage, safe_get
from utils.filters import normalize, looks_like_target
from utils.price_parser import extract_price_from_node

BASE_URL = "https://www.amazon.co.uk"

def _parse_search_items(html: str, model_query: str):
    soup = BeautifulSoup(html, "lxml")
    items = soup.select('div[data-component-type="s-search-result"]')
    results = []

    for it in items:
        asin = it.get('data-asin')
        h2 = it.select_one("a.a-link-normal h2")
        title = h2.get_text(strip=True) if h2 else ""
        url = None
        if h2:
            a = h2.find_parent("a", class_="a-link-normal")
            if a and a.has_attr("href"):
                url = BASE_URL + a["href"]
        if url and "/dp/" not in url:
            url = None
        price = extract_price_from_node(it)
        results.append({"asin": asin, "title": title, "url": url, "price": price})

    return [r for r in results if looks_like_target(r["title"], model_query)]

def scrape(model: str):
    s = build_session()
    prefetch_homepage(s, BASE_URL)
    search_url = f"{BASE_URL}/s?k={quote(model)}"
    html = safe_get(s, search_url)
    candidates = _parse_search_items(html, model)
    out = []
    for c in candidates:
        out.append({
            "site": "Amazon",
            "model": model,
            "title": c["title"],
            "price": c["price"] or "N/A",
            "url": c["url"],
        })
    return list({r["url"]: r for r in out if r["url"]}.values())
