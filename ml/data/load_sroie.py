import argparse

from ml.data.constants import DATASET_ID
from ml.data.sroie import load_sroie_dataset


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-id", default=DATASET_ID)
    args = parser.parse_args()
    dataset = load_sroie_dataset(args.dataset_id)
    print(dataset)
    for split, rows in dataset.items():
        print(split, rows.features, len(rows))
        print(rows.remove_columns(["image"])[0] if "image" in rows.column_names else rows[0])


if __name__ == "__main__":
    main()
