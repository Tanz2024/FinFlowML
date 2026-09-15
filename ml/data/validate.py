from collections.abc import Sequence


def validate_lengths(words: Sequence, ner_tags: Sequence, bboxes: Sequence) -> list[str]:
    lengths = (len(words), len(ner_tags), len(bboxes))
    return [] if len(set(lengths)) == 1 else [f"length_mismatch:{lengths[0]}/{lengths[1]}/{lengths[2]}"]


def duplicate_fingerprints(fingerprints_by_split: dict[str, list[str]]) -> dict[str, list[str]]:
    splits = list(fingerprints_by_split)
    duplicates = {}
    for position, left in enumerate(splits):
        for right in splits[position + 1 :]:
            overlap = sorted(set(fingerprints_by_split[left]) & set(fingerprints_by_split[right]))
            if overlap:
                duplicates[f"{left}_vs_{right}"] = overlap
    return duplicates
