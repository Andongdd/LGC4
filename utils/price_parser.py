from bs4 import Tag
from utils.filters import RRP_PAT

def extract_price_from_node(node: Tag):
    if node is None:
        return None
    off = node.select_one("span.a-price span.a-offscreen")
    if off:
        txt = off.get_text(strip=True)
        if txt and not RRP_PAT.search(txt):
            return txt
    whole = node.select_one("span.a-price-whole")
    frac  = node.select_one("span.a-price-fraction")
    if whole:
        w = whole.get_text(strip=True).replace(",", "")
        f = (frac.get_text(strip=True) if frac else "00")
        if w.isdigit():
            return f"£{w}.{f}"
    off2 = node.select_one("span.a-price span.a-offscreen")
    if off2:
        txt = off2.get_text(strip=True)
        if txt and not RRP_PAT.search(txt):
            return txt
    return None
