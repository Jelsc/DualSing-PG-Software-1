# Offline landmark ML scaffold

This package provides a CPU-capable starting point for consent-gated landmark-sequence training, participant-isolated evaluation, and ONNX export. It contains no sign samples, sign definitions, recordings, or claimed recognition results. Synthetic tests use only numeric tensors and opaque `test-class-*` labels.

## Quick path

Run checks in an isolated Docker container from the repository root. This does not use or modify Compose services and publishes no ports:

```powershell
docker build -f ml/Dockerfile -t dualsign-ml:phase7 .
docker run --rm --network none dualsign-ml:phase7
```

The container runs Ruff lint, Ruff format verification, pytest, and an ONNX Runtime CPU parity check. It uses Python 3.11 and pinned CPU-compatible dependencies.

## Dataset boundary

`load_npz_dataset` accepts a numeric-only NPZ archive with exactly these arrays:

| Array | Shape / contract |
| --- | --- |
| `features` | Float-compatible `(samples, frames, features)` landmark tensor |
| `lengths` | `(samples,)`, valid-frame counts in the padded tensor |
| `participant_ids` | Unicode/bytes pseudonyms using `participant_*` values |
| `sign_ids` | Opaque IDs all present in the caller-supplied validated catalog set |
| `consent_granted` | Boolean `(samples,)`, every value true |
| `audit_refs` | Non-empty opaque consent/audit references, one per sample |
| `schema_version` | One value equal to the active feature schema version |

Load with `allow_pickle=False`. The caller is responsible for obtaining the IDs from the Phase 2 catalog filtered to `validated` status and for resolving consent audit references through the consent/audit domain. Do not include names, contact details, raw video, or identifying metadata in this package or its dataset files.

The default schema is `dualsign-landmarks-v1`, with 1,629 numeric features per frame (543 landmarks × x/y/z) and per-sequence, per-feature z-score normalization over valid frames. Constant dimensions map to zero. `LandmarkExtractor` defines the future single-frame adapter shape, but this is not a working extractor or a claim that a particular MediaPipe runtime generates it. Select and demonstrate a compatible supported Python API before implementing one; callers retain frame ownership and this package stores no image/video data.

## Training and evaluation

`split_by_participant` deterministically assigns entire participants to train, validation, and test and requires at least three participants. `train_gru` is an initial PyTorch GRU baseline; callers own validation-based model selection and all catalog/data policy. The package exposes precision, recall, F1, confusion-matrix metrics, an inference-latency measurement hook, and `predict_with_unknown`.

The `UNKNOWN` helper requires a caller-provided confidence threshold. No production threshold is recommended here. Synthetic test outcomes are only contract checks and provide no evidence of useful sign recognition, accuracy, or runtime performance on devices.

`export_onnx` uses PyTorch 2.8's TorchScript ONNX exporter with `dynamic_axes` for batch and sequence dimensions. The dynamo exporter currently fails on this GRU model during `torch.export`; this scaffold uses the documented legacy path that was verified for this pinned runtime. The export checks the ONNX graph's symbolic dimensions. `check_onnx_parity` runs the exported model with ONNX Runtime's CPU provider and compares logits against PyTorch at multiple batch sizes and sequence lengths.

## Follow-up boundary

- Validate catalog IDs against a live/exported Phase 2 catalog and map consent audit references through the existing consent workflow.
- Demonstrate MediaPipe Python package/API and landmark compatibility before adding an extractor adapter.
- Collect appropriately consented, reviewed data before fitting or evaluating any meaningful model.
- Establish validation protocol, confidence calibration, deployment runtime compatibility, and device latency on representative real workloads before product use.

## Rollback boundary

The scaffold is isolated to `ml/`. Removing that directory removes its package, tests, Docker image definition, and documentation without affecting the application stack.
