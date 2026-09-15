from ml.data.sroie import document_fingerprint, process_example


class Feature:
    def int2str(self, value):
        return ["S-COMPANY", "S-DATE", "S-ADDRESS", "S-TOTAL", "O"][value]


class Split:
    column_names = ["words", "ner_tags", "bboxes"]
    features = {"ner_tags": type("FeatureInfo", (), {"feature": Feature()})()}

    def __init__(self, row): self.row = row
    def __len__(self): return 1
    def __getitem__(self, index): return self.row


def test_target_formatting_collects_all_tokens_in_order():
    row = {"words": ["ACME", "ROAD", "LTD"], "ner_tags": [0, 2, 0], "bboxes": [[], [], []]}
    item = process_example(Split(row), 0, "train")
    assert item.raw_targets["company"] == "ACME LTD"
    assert item.raw_targets["address"] == "ROAD"
    assert "multiple_regions:company" in item.validation_issues


def test_malformed_lengths_are_marked():
    row = {"words": ["ACME"], "ner_tags": [0, 4], "bboxes": [[]]}
    item = process_example(Split(row), 0, "train")
    assert item.malformed is True


def test_fingerprint_is_content_based():
    assert document_fingerprint(["ACME", "TOTAL"]) == document_fingerprint(["ACME", "TOTAL"])
