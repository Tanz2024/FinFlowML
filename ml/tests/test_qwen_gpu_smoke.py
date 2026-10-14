import json
import subprocess
import sys


def test_smoke_requires_inputs_and_returns_failure_evidence(tmp_path):
    evidence = tmp_path / "evidence.json"
    result = subprocess.run(
        [sys.executable, "scripts/qwen_gpu_smoke.py", "--evidence", str(evidence)],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 1
    payload = json.loads(evidence.read_text())
    assert payload["status"] == "failed"
    assert "--image and --adapter" in payload["error"]


def test_smoke_cli_keeps_model_stack_out_of_parent_process():
    source = open("scripts/qwen_gpu_smoke.py", encoding="utf-8").read()
    assert "import torch" in source
    assert source.index("import torch") > source.index("def _model_stage")
