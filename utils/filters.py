import re

NEGATIVE_KWS = re.compile(
    r'(stand|bracket|mount|wall|cover|remote|protector|screen|glass|soundbar|hdmi|cable|monitor|'
    r'replacement|case|gift\s*card|warranty|insurance|subscription|voucher|gaming\s*monitor)',
    re.I
)
RRP_PAT = re.compile(r'\b(RRP|List Price|Was|R\.R\.P)\b', re.I)

def normalize(text: str) -> str:
    return re.sub(r"[\s\-_/]+", "", text or "").upper()

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
