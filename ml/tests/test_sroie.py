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


def test_train_loader_downloads_only_train_shards(monkeypatch):
    import ml.data.sroie as sroie

    requested = []
    loaded = []

    def fake_list_repo_files(dataset_id, repo_type):
        assert repo_type == "dataset"
        return ["README.md", "data/test-00000-of-00001.parquet", "data/train-00000-of-00001.parquet"]

    def fake_download(dataset_id, filename, repo_type):
        requested.append(filename)
        assert "test-" not in filename
        return f"/cache/{filename.rsplit('/', 1)[-1]}"

    def fake_load_dataset(dataset_id, **kwargs):
        loaded.append((dataset_id, kwargs))
        assert dataset_id == "parquet"
        assert kwargs["split"] == "train"
        assert all("test-" not in path for path in kwargs["data_files"])
        return "train-only"

    monkeypatch.setattr(sroie, "list_repo_files", fake_list_repo_files)
    monkeypatch.setattr(sroie, "hf_hub_download", fake_download)
    monkeypatch.setattr(sroie, "load_dataset", fake_load_dataset)

    assert sroie.load_sroie_dataset("mp-02/sroie", split="train") == "train-only"
    assert requested == ["data/train-00000-of-00001.parquet"]
    assert loaded[0][1]["data_files"] == ["/cache/train-00000-of-00001.parquet"]


def test_train_loader_preserves_label_feature_metadata(monkeypatch):
    import ml.data.sroie as sroie

    class ClassLabel:
        def int2str(self, value):
            return ["S-COMPANY", "S-DATE", "S-ADDRESS", "S-TOTAL", "O"][value]

    class TrainDataset:
        features = {"ner_tags": type("FeatureInfo", (), {"feature": ClassLabel()})()}

    monkeypatch.setattr(sroie, "list_repo_files", lambda *_args, **_kwargs: ["data/train-0.parquet"])
    monkeypatch.setattr(sroie, "hf_hub_download", lambda *_args, **_kwargs: "/cache/train-0.parquet")
    monkeypatch.setattr(sroie, "load_dataset", lambda *_args, **_kwargs: TrainDataset())

    dataset = sroie.load_sroie_dataset(split="train")
    assert [dataset.features["ner_tags"].feature.int2str(index) for index in range(5)] == [
        "S-COMPANY", "S-DATE", "S-ADDRESS", "S-TOTAL", "O"
    ]
