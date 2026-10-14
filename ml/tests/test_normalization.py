from ml.data.normalize import normalize_date, normalize_target, normalize_total


def test_normalization_is_conservative():
    assert normalize_target("company", "  ACME   SDN BHD ") == "acme sdn bhd"
    assert normalize_target("address", "A  Road\nJohor") == "a road johor"
    assert normalize_total("RM 1,234.50") == "1234.50"
    assert normalize_date("25/12/2018") == "2018-12-25"
    assert normalize_date("15/01/201911:05:16AM") == "2019-01-15"
    assert normalize_date("31/02/2019") == "31/02/2019"
    assert normalize_date("01/02/19") == "01/02/19"
    assert normalize_date("not-a-date") == "not-a-date"
