from ml.data.constants import TARGET_FIELDS


def build_prompt(ocr_text: str) -> str:
    fields = "\n".join(f"- {field}" for field in TARGET_FIELDS)
    return (
        "Extract these fields from the financial document:\n\n"
        f"{fields}\n\n"
        'Return only a JSON object with exactly these fields. All non-null field values '
        'must be JSON strings, including total (for example: "total": "193.00"). '
        "Do not invent information. If a field is unavailable, return null.\n\n"
        f"Receipt text:\n{ocr_text}"
    )
