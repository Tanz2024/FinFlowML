from ml.extraction.parser import parse_prediction


def test_parser_accepts_exact_schema_and_nulls():
    prediction, error = parse_prediction('{"company": null, "date": "2020-01-01", "address": null, "total": "10.00"}')
    assert error is None and prediction["company"] is None


def test_parser_accepts_string_integer_and_float_totals():
    template = '{"company": null, "date": null, "address": null, "total": %s}'
    for raw_total, expected in [("\"193.00\"", "193.00"), ("193", "193"), ("193.0", "193")]:
        prediction, error = parse_prediction(template % raw_total)
        assert error is None and prediction["total"] == expected


def test_parser_rejects_numeric_non_total_fields():
    for field in ("company", "date", "address"):
        raw = '{"company": null, "date": null, "address": null, "total": null}'
        prediction, error = parse_prediction(raw.replace(f'"{field}": null', f'"{field}": 123'))
        assert prediction is None and error == "invalid_schema:values_must_be_string_or_null"


def test_parser_marks_invalid_output():
    prediction, error = parse_prediction("not json")
    assert prediction is None and error is not None
    prediction, error = parse_prediction('{"company": "x"}')
    assert prediction is None and error.startswith("invalid_schema")
