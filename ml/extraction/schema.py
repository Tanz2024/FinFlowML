from dataclasses import dataclass
from typing import Any

from ml.data.constants import TARGET_FIELDS


@dataclass(frozen=True)
class ExtractionExample:
    split: str
    index: int
    fingerprint: str
    raw_targets: dict[str, str | None]
    normalized_targets: dict[str, str | None]
    malformed: bool
    validation_issues: tuple[str, ...]
    image_reference: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "split": self.split,
            "index": self.index,
            "fingerprint": self.fingerprint,
            "raw_targets": self.raw_targets,
            "normalized_targets": self.normalized_targets,
            "malformed": self.malformed,
            "validation_issues": list(self.validation_issues),
            "image_reference": self.image_reference,
        }


def empty_targets() -> dict[str, str | None]:
    return {field: None for field in TARGET_FIELDS}
