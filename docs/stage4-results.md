# Stage 4 completion and benchmark results

## Verification status

The completed Google Colab artifacts were located locally at:

`/Users/tanz/Downloads/drive-download-20261013T064938Z-1-001/`

They are intentionally not copied into Git. The directory contains `report.json`,
`evaluation_manifest.json`, complete base/adapter predictions, and the two
incremental checkpoint files. The repository contains the model-free verifier:

```bash
python -m ml.evaluation.verify_stage4_artifacts \
  /path/to/downloaded-evaluation-directory
```

The verifier checks that both complete prediction files contain the same 347
document identities and fingerprints, that partial checkpoints equal their
completed files, that manifest/configuration data agrees, and that report
summaries and paired counts recompute from predictions.

## Verified benchmark

| Metric | Base | Fine-tuned adapter |
|---|---:|---:|
| Macro field accuracy | 71.54% | 88.83% |
| All fields correct | 83/347 (23.92%) | 233/347 (67.15%) |
| JSON validity | 100% | 100% |
| Mean latency | 10.19 s | 15.10 s |

Field accuracy improved as follows:

| Field | Base | Adapter |
|---|---:|---:|
| Company | 69.45% | 88.18% |
| Date | 86.46% | 96.54% |
| Address | 42.07% | 78.10% |
| Total | 88.18% | 92.51% |

The paired report records 197 documents improved, 6 regressed, and 144
unchanged. These are verified properties of the downloaded report, not a new
local inference run.

The recorded runtime was Python 3.13.15, PyTorch 2.14.1, Transformers 4.57.6,
PEFT 0.21.1, bitsandbytes 0.50.2, CUDA 13.0 on a Tesla T4. The pinned base
revision was `cdbee75f17c01a7cc42f958dc650907174af0554`; the recorded dataset
revision was `f845db1c2ccaf883550320fe450d1e723374be32`.

## Integrity qualification

Exact OCR-word fingerprints had zero train/test overlap. However, the report
also identified 119 train/test target-text pairs at the configured similarity
threshold, involving 50 distinct test receipts; six pairs had identical target
field text. This is evidence of repeated or highly similar labels, not proof
of image duplication or model leakage. Target fields omit much of the receipt
image and can repeat for legitimate reasons such as the same merchant,
template, address, and transaction pattern.

Because the historical training dataset revision was not preserved, the result
cannot be described as proven leakage-free. The correct conclusion is:

- exact fingerprint contamination was not observed in the evaluated snapshot;
- target-text near-duplicates are present and may make some test examples less
  independent;
- whether those pairs are distinct receipts or historical contamination
  requires comparing the original training snapshot's raw images/rows.

## Environment notes

The Colab run required a compatible CUDA environment. The reproducible setup
must install the pinned training/evaluation requirements before importing
PyTorch. Colab runtime changes can otherwise produce NumPy ABI warnings or
torchvision import failures; torchvision is not required by this OCR-text
benchmark and should not be imported as part of evaluation. If a runtime has a
NumPy/torchvision mismatch, restart the runtime after dependency installation
and rerun the preflight cells before evaluating.

## Limitations

- No original training dataset commit was recorded.
- No raw image-level near-duplicate analysis was available from the saved
  artifacts.
- The benchmark is one fixed test run and does not establish confidence
  intervals.
- The adapter improves accuracy but increases mean generation latency by about
  4.91 seconds per receipt on the recorded T4 runtime.
- Raw predictions, model weights, adapters, checkpoints, and secrets remain
  outside public Git.
