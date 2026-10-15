from ml.data.normalize import normalize_date, normalize_target, normalize_total
from backend.app.services.currency import detect_explicit_currency


def test_normalization_is_conservative():
    assert normalize_target("company", "  ACME   SDN BHD ") == "acme sdn bhd"
    assert normalize_target("address", "A  Road\nJohor") == "a road johor"
    assert normalize_total("RM 1,234.50") == "1234.50"
    assert normalize_date("25/12/2018") == "2018-12-25"
    assert normalize_date("15/01/201911:05:16AM") == "2019-01-15"
    assert normalize_date("31/02/2019") == "31/02/2019"
    assert normalize_date("01/02/19") == "01/02/19"
    assert normalize_date("not-a-date") == "not-a-date"


def test_currency_detection_requires_one_explicit_marker():
    assert detect_explicit_currency("TOTAL RM 12.50") == "MYR"
    assert detect_explicit_currency("USD 12.50") == "USD"
    assert detect_explicit_currency("US$ 12.50") == "USD"
    assert detect_explicit_currency("EUR 12.50") == "EUR"
    assert detect_explicit_currency("€12.50") == "EUR"
    assert detect_explicit_currency("GBP 12.50") == "GBP"
    assert detect_explicit_currency("£12.50") == "GBP"
    assert detect_explicit_currency("SGD 12.50") == "SGD"
    assert detect_explicit_currency("AUD 12.50") == "AUD"
    assert detect_explicit_currency("CAD 12.50") == "CAD"
    assert detect_explicit_currency("12.50") is None
    assert detect_explicit_currency("$12.50") is None
    assert detect_explicit_currency("RM 12.50 USD 3.00") is None
    assert detect_explicit_currency("company address, total 12.50") is None
    assert detect_explicit_currency("MYR 12.50", "USD 12.50") is None
