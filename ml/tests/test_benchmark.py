from ml.evaluation.benchmark import runtime_metadata


def test_benchmark_configuration():
    class Model:
        revision = "abc"
        device = "cpu"
        dtype = "torch.float32"

    metadata = runtime_metadata(Model(), 128)
    assert metadata["model_id"] == "Qwen/Qwen3-4B-Instruct-2507"
    assert metadata["generation"] == {"do_sample": False, "max_new_tokens": 128}
