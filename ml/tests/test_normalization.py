from ml.data.normalize import normalize_date, normalize_target, normalize_total


def test_normalization_is_conservative():
    assert normalize_target("company", "  ACME   SDN BHD ") == "acme sdn bhd"
    assert normalize_target("address", "A  Road\nJohor") == "a road johor"
    assert normalize_total("RM 1,234.50") == "1234.50"
    assert normalize_date("25/12/2018") == "2018-12-25"
    assert normalize_date("not-a-date") == "not-a-date"
