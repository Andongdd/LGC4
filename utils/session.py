import random
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import time

UA_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
]

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Upgrade-Insecure-Requests": "1",
    "DNT": "1",
    "Connection": "keep-alive",
}

TIMEOUT = 20

def build_session() -> requests.Session:
    s = requests.Session()
    headers = DEFAULT_HEADERS.copy()
    headers["User-Agent"] = random.choice(UA_POOL)
    s.headers.update(headers)

    retry = Retry(
        total=5, connect=3, read=3,
        backoff_factor=1.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS"],
        raise_on_status=True,
    )
    adapter = HTTPAdapter(max_retries=retry)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    return s

def jitter_sleep(a=0.7, b=1.6):
    time.sleep(random.uniform(a, b))

def safe_get(s: requests.Session, url: str) -> str:
    jitter_sleep()
    r = s.get(url, timeout=TIMEOUT)
    r.raise_for_status()
    return r.text

def prefetch_homepage(s: requests.Session, base_url: str):
    try:
        s.get(base_url, timeout=TIMEOUT)
        jitter_sleep()
        s.headers["Referer"] = base_url + "/"
    except:
        pass
