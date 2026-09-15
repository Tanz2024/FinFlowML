import random
from typing import TypeVar

T = TypeVar("T")


def split_indices(size: int, validation_fraction: float = 0.1, seed: int = 42) -> tuple[list[int], list[int]]:
    indices = list(range(size))
    random.Random(seed).shuffle(indices)
    validation_size = round(size * validation_fraction)
    return sorted(indices[validation_size:]), sorted(indices[:validation_size])


def split_examples(examples: list[T], validation_fraction: float = 0.1, seed: int = 42) -> tuple[list[T], list[T]]:
    train_indices, validation_indices = split_indices(len(examples), validation_fraction, seed)
    return [examples[index] for index in train_indices], [examples[index] for index in validation_indices]
