"""Currency and amount normalization helpers shared by ingestion services."""

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

DEFAULT_CURRENCY = "USD"

_CURRENCY_ALIASES = {
    "$": "USD",
    "US$": "USD",
    "USD": "USD",
    "EUR": "EUR",
    "€": "EUR",
    "GBP": "GBP",
    "£": "GBP",
}


def normalize_currency(currency: str | None) -> str:
    """Map a raw OCR/extraction currency token to a 3-letter ISO code."""
    if not currency:
        return DEFAULT_CURRENCY
    token = currency.strip().upper()
    return _CURRENCY_ALIASES.get(token, token[:3] if len(token) >= 3 else DEFAULT_CURRENCY)


def normalize_amount(amount: Decimal | str | float | None) -> Decimal:
    """Coerce a raw extracted amount into a 2-decimal Decimal, defaulting to 0.00."""
    if amount is None:
        return Decimal("0.00")
    try:
        value = amount if isinstance(amount, Decimal) else Decimal(str(amount))
    except InvalidOperation:
        return Decimal("0.00")
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
