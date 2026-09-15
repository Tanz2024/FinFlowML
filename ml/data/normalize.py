import re
from decimal import Decimal, InvalidOperation


def collapse_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def normalize_text(value: str | None, *, casefold: bool = True) -> str | None:
    if value is None:
        return None
    normalized = collapse_whitespace(value)
    return normalized.casefold() if casefold else normalized


def normalize_total(value: str | None) -> str | None:
    if value is None:
        return None
    text = collapse_whitespace(value).casefold()
    text = re.sub(r"(?:rm|myr|usd|eur|gbp|[$€£])", "", text)
    text = re.sub(r"[^0-9,.-]", "", text)
    if not text:
        return collapse_whitespace(value).casefold()
    if "," in text and "." in text:
        text = text.replace(",", "") if text.rfind(".") > text.rfind(",") else text.replace(".", "").replace(",", ".")
    elif "," in text:
        parts = text.split(",")
        text = "".join(parts) if len(parts[-1]) == 3 and len(parts) > 1 else ".".join(parts)
    try:
        return format(Decimal(text).quantize(Decimal("0.01")), "f")
    except InvalidOperation:
        return collapse_whitespace(value).casefold()


def normalize_date(value: str | None) -> str | None:
    if value is None:
        return None
    text = collapse_whitespace(value)
    for pattern in (r"(\d{1,2})/(\d{1,2})/(\d{4})", r"(\d{1,2})-(\d{1,2})-(\d{4})"):
        match = re.fullmatch(pattern, text)
        if match:
            day, month, year = map(int, match.groups())
            if 1 <= day <= 31 and 1 <= month <= 12:
                return f"{year:04d}-{month:02d}-{day:02d}"
    return text.casefold()


def normalize_target(field: str, value: str | None) -> str | None:
    if field == "total":
        return normalize_total(value)
    if field == "date":
        return normalize_date(value)
    return normalize_text(value)
