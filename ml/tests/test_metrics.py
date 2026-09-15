from ml.evaluation.metrics import metrics


def test_metrics_and_missing_behavior():
    expected = {"company": "ACME", "date": "25/12/2018", "address": "A Road", "total": "RM 10.00"}
    predicted = {"company": "acme", "date": "2018-12-25", "address": "A Road", "total": "10"}
    result = metrics(expected, predicted)
    assert result["raw_exact_match"]["company"] is False
    assert result["normalized_exact_match"]["company"] is True
    assert result["normalized_exact_match"]["date"] is True
    assert result["document_all_fields_correct"] is True
    assert metrics({"company": None}, {"company": None})["raw_exact_match"]["company"] is False
