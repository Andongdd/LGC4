# scrapers/amazon.py
import re
import time
import random
from urllib.parse import quote

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup

BASE_URL = "https://www.amazon.co.uk"

# 多个真实 UA 轮换（可再自行补充）
UA_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
]

DEFAULT_HEADERS = {
    "User-Agent": random.choice(UA_POOL),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Upgrade-Insecure-Requests": "1",
    "DNT": "1",
    "Connection": "keep-alive",
}

TIMEOUT = 20

NEGATIVE_KWS = re.compile(
    r'(stand|bracket|mount|wall|cover|remote|protector|screen|glass|soundbar|hdmi|cable|monitor|'
    r'replacement|case|gift\s*card|warranty|insurance|subscription|voucher|gaming\s*monitor)',
    re.I
)
RRP_PAT = re.compile(r'\b(RRP|List Price|Was|R\.R\.P)\b', re.I)
SIZE_PATTERNS = [r'\b55\b', r'55"', r'\b55-?INCH\b', r'\b55IN\b', r'OLED55']


# -------- Session with retries & jitter --------
def _build_session() -> requests.Session:
    s = requests.Session()
    # 每次 session 选一个 UA，后续请求一致，降低指纹异常
    h = DEFAULT_HEADERS.copy()
    h["User-Agent"] = random.choice(UA_POOL)
    s.headers.update(h)

    retry = Retry(
        total=5,
        connect=3,
        read=3,
        backoff_factor=1.5,             # 指数退避：1.5, 2.25, 3.38, ...
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS"],
        raise_on_status=True,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=10, pool_maxsize=10)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    return s


def _jitter_sleep(a=0.7, b=1.6):
    time.sleep(random.uniform(a, b))


def _prefetch_home(s: requests.Session):
    """
    先访问首页，获取区域/语言/同意页等 Cookie，以提高后续成功率。
    """
    try:
        s.get(BASE_URL, timeout=TIMEOUT)
        _jitter_sleep()
        # referer 有时也有帮助
        s.headers["Referer"] = BASE_URL + "/"
    except Exception:
        pass  # 失败也不致命，继续走


def _safe_get(s: requests.Session, url: str) -> str:
    """
    GET + 自动抖动，失败抛出 HTTPError 让上游感知。
    """
    _jitter_sleep()  # 避免连发
    r = s.get(url, timeout=TIMEOUT)
    r.raise_for_status()
    return r.text


# -------- Utilities --------
def normalize(s: str) -> str:
    return re.sub(r"[\s\-_/]+", "", s or "").upper()


def looks_like_target(title: str, model_query: str) -> bool:
    if not title:
        return False
    t = title.upper()

    # ---- 1. 品牌/型号 ----
    has_lg = "LG" in t
    has_model_prefix = bool(re.search(r"OLED(55|65)(C4|B4)", t))
    if not (has_lg or has_model_prefix):
        return False

    # ---- 2. 系列 ----
    series_tokens = []
    if "C4" in model_query.upper():
        series_tokens.append("C4")
    if "B4" in model_query.upper():
        series_tokens.append("B4")
    if not series_tokens:
        series_tokens = ["C4", "B4"]

    if not any(tok in t for tok in series_tokens):
        return False

    # ---- 3. 尺寸 ----
    # 从 model_query 抽尺寸（默认65）
    m = re.search(r"(55|65)", model_query)
    size = m.group(1) if m else "65"
    size_patterns = [
        rf"\b{size}\b",
        rf"{size}\"",
        rf"\b{size}-?INCH\b",
        rf"\b{size}IN\b",
        rf"OLED{size}"
    ]
    if not any(re.search(p, t, re.I) for p in size_patterns):
        return False

    # ---- 4. 负面关键词 ----
    if NEGATIVE_KWS.search(title):
        return False

    return True


def extract_price_from_node(node):
    if node is None:
        return None
    # 1) 优先：offscreen（排除 RRP/Was）
    off = node.select_one("span.a-price span.a-offscreen")
    if off:
        txt = off.get_text(strip=True)
        if txt and not RRP_PAT.search(txt):
            return txt
    # 2) 兜底：拼接 whole + fraction
    whole = node.select_one("span.a-price-whole")
    frac  = node.select_one("span.a-price-fraction")
    if whole:
        w = whole.get_text(strip=True).replace(",", "")
        f = (frac.get_text(strip=True) if frac else "00")
        if w.isdigit():
            return f"£{w}.{f}"
    # 3) 再兜底：任何非 RRP 的 offscreen
    off2 = node.select_one("span.a-price span.a-offscreen")
    if off2:
        txt = off2.get_text(strip=True)
        if txt and not RRP_PAT.search(txt):
            return txt
    return None


# -------- Parsing --------
def _parse_search_items(html: str, model_query: str):
    soup = BeautifulSoup(html, "lxml")
    items = soup.select('div[data-component-type="s-search-result"]')
    results, seen_asin = [], set()

    for it in items:
        asin = it.get('data-asin')
        if asin and asin in seen_asin:
            continue

        # 标题节点
        h2 = it.select_one("a.a-link-normal h2")
        title = h2.get_text(strip=True) if h2 else ""

        # 链接：先回溯父 a，再尝试 h2 内部 a
        url = None
        if h2:
            a_parent = h2.find_parent("a", class_="a-link-normal")
            if a_parent and a_parent.has_attr("href"):
                url = BASE_URL + a_parent["href"]
            if not url:
                a_child = h2.select_one("a.a-link-normal")
                if a_child and a_child.has_attr("href"):
                    url = BASE_URL + a_child["href"]

        # 仅接受 /dp/ 详情链接
        if url and "/dp/" not in url:
            url = None

        price = extract_price_from_node(it)

        if asin:
            seen_asin.add(asin)

        results.append({"asin": asin, "title": title, "url": url, "price": price})

    # 粗筛
    results = [r for r in results if looks_like_target(r["title"], model_query)]
    return results


def _verify_detail(s: requests.Session, url: str, model_query: str):
    if not url:
        return None
    html = _safe_get(s, url)
    soup = BeautifulSoup(html, "lxml")

    title_el = soup.select_one('#productTitle') or soup.select_one('h1#title')
    title = title_el.get_text(strip=True) if title_el else ""

    blob = " ".join(x.get_text(separator=" ", strip=True) for x in soup.select(
        '#productDetails_techSpec_section_1 tr, #detailBullets_feature_div li, table.prodDetTable tr, #feature-bullets li'
    ))
    blob_u = f"{title} {blob}".upper()

    # ---- 品牌 ----
    brand_ok = ('LG' in blob_u or 'LG' in normalize(title))

    # ---- 尺寸（只接受 55 或 65） ----
    if "55" in model_query:
        size_patterns = [r"\b55\b", r'55"', r"\b55-?INCH\b", r"\b55IN\b", r"OLED55"]
    else:
        size_patterns = [r"\b65\b", r'65"', r"\b65-?INCH\b", r"\b65IN\b", r"OLED65"]

    size_ok = any(re.search(p, blob_u, re.I) for p in size_patterns)

    # ---- 系列 ----
    series_ok = bool(re.search(r'\b(C4|B4)\b', blob_u))
    model_ok  = bool(re.search(r'(OLED55|OLED65)(C4|B4)', blob_u))

    # ---- 最终核验 ----
    if not (brand_ok and size_ok and (model_ok or series_ok)):
        return None

    # ---- 价格兜底 ----
    price_region = soup.select_one('#corePriceDisplay_desktop_feature_div') or soup
    price = extract_price_from_node(price_region)

    return {"title": title or None, "price": price or None, "verified": True}


# -------- Public API --------
def scrape(model: str, verify: bool = True):
    """
    搜索并返回：
    {site, model, title, price, url}
    带反爬缓解（Session、Cookies 预热、重试、抖动）。
    """
    s = _build_session()
    _prefetch_home(s)  # 预热 Cookie/地区
    search_url = f"{BASE_URL}/s?k={quote(model)}"

    # 首次请求可能命中 503；由 Retry 控制自动重试，仍失败会抛出异常
    html = _safe_get(s, search_url)
    candidates = _parse_search_items(html, model)

    out = []
    for c in candidates:
        title, price = c["title"], (c["price"] or "N/A")
        # if verify:
        #     v = _verify_detail(s, c["url"], model)
        #     if not v:
        #         continue
        #     title = v["title"] or title
        #     price = v["price"] or price

        out.append({
            "site": "Amazon",
            "model": model,
            "title": title,
            "price": price,
            "url": c["url"],
        })

    # URL 去重
    uniq = {row["url"]: row for row in out if row["url"]}.values()
    return list(uniq)


# 本地调试
if __name__ == "__main__":
    for m in ["LG OLED55C4", "LG OLED55B4"]:
        rows = scrape(m, verify=True)
        print(f"\n>>> {m}")
        for r in rows:
            print(r["price"], "-", r["title"], "-", r["url"])
