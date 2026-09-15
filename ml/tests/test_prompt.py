from ml.extraction.prompt import build_prompt


def test_prompt_contains_ocr_only_and_schema_instruction():
    prompt = build_prompt("ACME TOTAL 10.00")
    assert "ACME TOTAL 10.00" in prompt
    assert "company" in prompt and "return null" in prompt.lower()
    assert "ner_tags" not in prompt and "raw_targets" not in prompt
