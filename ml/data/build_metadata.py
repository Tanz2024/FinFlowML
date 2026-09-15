import argparse
import json
from pathlib import Path

from ml.data.constants import DATASET_ID, DEFAULT_SEED
from ml.data.split import split_examples
from ml.data.sroie import load_sroie_dataset, process_split
from ml.evaluation.report import dataset_statistics


def build_metadata(dataset_id: str = DATASET_ID, output: Path = Path("data/processed/sroie_metadata.json")) -> dict:
    dataset = load_sroie_dataset(dataset_id)
    official_test = process_split(dataset["test"], "test")
    training = process_split(dataset["train"], "source_train")
    train, validation = split_examples(training, seed=DEFAULT_SEED)
    splits = {"train": train, "validation": validation, "test": official_test}
    report = {"dataset": dataset_id, "seed": DEFAULT_SEED, "statistics": dataset_statistics(splits), "examples": {name: [item.to_dict() for item in values] for name, values in splits.items()}}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-id", default=DATASET_ID)
    parser.add_argument("--output", type=Path, default=Path("data/processed/sroie_metadata.json"))
    args = parser.parse_args()
    report = build_metadata(args.dataset_id, args.output)
    stats = report["statistics"]
    print(f"Dataset: {report['dataset']}\n")
    print(f"Original/processed splits: {stats['split_counts']}")
    print(f"Targets in train: {stats['target_counts_train']}")
    print(f"Malformed examples: {stats['malformed_examples']}")
    print(f"Cross-split duplicate fingerprints: {sum(map(len, stats['cross_split_duplicate_fingerprints'].values()))}")


if __name__ == "__main__":
    main()
