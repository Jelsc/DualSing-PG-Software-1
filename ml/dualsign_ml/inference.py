"""Deterministic ONNX evaluation seam for the synthetic MVP scaffold."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import onnxruntime as ort

from .evaluation import predict_with_unknown
from .schema import LandmarkSchema


@dataclass(frozen=True)
class InferenceResult:
    labels: tuple[str, ...]
    model_version: str
    schema_version: str
    inference_source: str = "synthetic_scaffold"


def evaluate_onnx(
    model_path: str | Path,
    sequences: np.ndarray,
    lengths: np.ndarray,
    classes: list[str] | tuple[str, ...],
    *,
    schema: LandmarkSchema,
    confidence_threshold: float = 0.7,
    model_version: str = "synthetic-gru-v1",
) -> InferenceResult:
    labels = tuple(classes)
    if not labels or len(labels) != len(set(labels)) or "UNKNOWN" in labels:
        raise ValueError("classes must be non-empty, unique, and exclude UNKNOWN")
    normalized = schema.normalize(sequences, lengths)
    session = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
    input_names = {item.name for item in session.get_inputs()}
    if input_names != {"sequences", "lengths"}:
        raise ValueError("ONNX model inputs must be sequences and lengths")
    outputs: Any = session.run(None, {"sequences": normalized, "lengths": lengths.astype(np.int64)})
    logits = np.asarray(outputs[0])
    if logits.ndim != 2 or logits.shape[1] != len(labels):
        raise ValueError("ONNX output classes do not match the declared class list")
    logits = logits - logits.max(axis=1, keepdims=True)
    probabilities = np.exp(logits)
    probabilities /= probabilities.sum(axis=1, keepdims=True)
    if probabilities.ndim != 2 or probabilities.shape[1] != len(labels):
        raise ValueError("ONNX output classes do not match the declared class list")
    return InferenceResult(
        labels=tuple(
            predict_with_unknown(probabilities, labels, confidence_threshold=confidence_threshold)
        ),
        model_version=model_version,
        schema_version=schema.version,
    )
