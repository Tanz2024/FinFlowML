# Stage 4 adapter evaluation

This evaluation is separate from training and from the existing Stage 3
baseline reports. It loads the pinned Qwen revision and a pre-trained PEFT
adapter, then evaluates both on the identical 347-document official SROIE
test split. It does not tune prompts, select checkpoints, or write to the
adapter directory or `results/baseline/`.

The runner is `ml/evaluation/stage4_adapter_benchmark.py`. It reuses the
repository's SROIE loader, content fingerprints, prompt, parser, normalization,
and metrics. It writes only to the new output directory supplied by `--output`
(default: `results/stage4_evaluation/`): `report.json`,
`base_predictions.json`, and `adapter_predictions.json`.

## Minimal Colab procedure

Run in a fresh CUDA Colab runtime. Do not run `ml.training.train`.

```bash
%cd /content
!git clone https://github.com/Tanz2024/FinFlowML.git
%cd /content/FinFlowML
!pip install -r requirements-training.txt
```

Copy the already-trained adapter into a separate read-only evaluation location
or point directly at the existing directory. Do not place outputs inside it:

```bash
export ADAPTER_PATH=/content/drive/MyDrive/FinFlowML-stage4-final-v2/best_adapter
export EVAL_OUTPUT=/content/drive/MyDrive/FinFlowML-stage4-evaluation
```

Validate the adapter artifacts without loading the model:

```bash
test -f "$ADAPTER_PATH/adapter_config.json"
test -f "$ADAPTER_PATH/adapter_model.safetensors" -o -f "$ADAPTER_PATH/adapter_model.bin"
```

Run the paired benchmark:

```bash
!python -m ml.evaluation.stage4_adapter_benchmark \
  --adapter "$ADAPTER_PATH" \
  --output "$EVAL_OUTPUT" \
  --dataset-revision "<DATASET_COMMIT_SHA>"
```

Replace `<DATASET_COMMIT_SHA>` with the dataset commit shown by the Colab
dataset download/logging step. If the dataset source is intentionally left at
the default revision, pass `--dataset-revision` with the recorded commit or
omit it and the report will say `not supplied`.

The command must report CUDA hardware and exactly 347 test documents. The
report records model revision, adapter path/provenance, package versions,
hardware, split fingerprints, exact and near-duplicate checks, decoding
configuration, field metrics, JSON validity, latency, error counts, and
per-document paired changes.

The benchmark uses `device_map={"": 0}`, NF4 4-bit bitsandbytes loading,
double quantization, and BF16 when the GPU supports it, otherwise FP16.
Generation is deterministic: `do_sample=False`, `max_new_tokens=192`.

## Interpretation safeguards

- The official test split is never loaded by the training runner in this
  evaluation path and is not used for tuning or checkpoint selection.
- The adapter is the externally supplied Colab artifact; the local repository
  does not contain or recreate it.
- A locally prepared runner is not evidence of execution. Only the generated
  Colab `report.json` and prediction files constitute benchmark evidence.
- Preserve the original `results/baseline/*.json` files for comparison.
