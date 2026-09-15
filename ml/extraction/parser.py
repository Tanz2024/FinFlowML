import json
from decimal import Decimal, InvalidOperation
from typing import Any

from ml.data.constants import TARGET_FIELDS


def empty_prediction() -> dict[str, str | None]:
    return {field: None for field in TARGET_FIELDS}


def parse_prediction(raw_response: str) -> tuple[dict[str, str | None] | None, str | None]:
    try:
        value: Any = json.loads(raw_response)
    except json.JSONDecodeError as exc:
        return None, f"invalid_json:{exc.msg}"
    if not isinstance(value, dict) or set(value) != set(TARGET_FIELDS):
        return None, "invalid_schema:expected_exact_target_fields"
    for field, item in value.items():
        if item is None or isinstance(item, str):
            continue
        if field == "total" and isinstance(item, (int, float)) and not isinstance(item, bool):
            try:
                value[field] = format(Decimal(str(item)).normalize(), "f")
            except InvalidOperation:
                return None, "invalid_schema:total_number_is_not_finite"
            continue
        return None, "invalid_schema:values_must_be_string_or_null"
    return {field: value[field] for field in TARGET_FIELDS}, None
