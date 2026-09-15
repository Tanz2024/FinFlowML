from ml.data.split import split_indices


def test_deterministic_split():
    assert split_indices(20, seed=7) == split_indices(20, seed=7)
    train, validation = split_indices(20, seed=7)
    assert not set(train) & set(validation)
    assert sorted(train + validation) == list(range(20))
