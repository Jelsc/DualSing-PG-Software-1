"""Classification metrics, explicit UNKNOWN policy, and latency measurement hooks."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from time import perf_counter

import numpy as np


@dataclass(frozen=True)
class ClassMetrics:
    precision: float
    recall: float
    f1: float
    support: int


@dataclass(frozen=True)
class EvaluationMetrics:
    labels: tuple[str, ...]
    confusion_matrix: tuple[tuple[int, ...], ...]
    per_class: dict[str, ClassMetrics]
    macro_precision: float
    macro_recall: float
    macro_f1: float


def classification_metrics(
    actual: Sequence[str], predicted: Sequence[str], labels: Sequence[str]
) -> EvaluationMetrics:
    class_labels = tuple(labels)
    if not class_labels or len(class_labels) != len(set(class_labels)):
        raise ValueError("labels must be non-empty and unique")
    if len(actual) != len(predicted) or not actual:
        raise ValueError("actual and predicted must have the same non-zero length")
    if set(actual) - set(class_labels) or set(predicted) - set(class_labels):
        raise ValueError("all actual and predicted values must be listed in labels")
    matrix = np.zeros((len(class_labels), len(class_labels)), dtype=np.int64)
    indices = {label: index for index, label in enumerate(class_labels)}
    for truth, guess in zip(actual, predicted, strict=True):
        matrix[indices[truth], indices[guess]] += 1
    per_class: dict[str, ClassMetrics] = {}
    for index, label in enumerate(class_labels):
        true_positive = int(matrix[index, index])
        precision = true_positive / int(matrix[:, index].sum()) if matrix[:, index].sum() else 0.0
        recall = true_positive / int(matrix[index, :].sum()) if matrix[index, :].sum() else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_class[label] = ClassMetrics(precision, recall, f1, int(matrix[index, :].sum()))
    return EvaluationMetrics(
        class_labels,
        tuple(tuple(int(value) for value in row) for row in matrix),
        per_class,
        float(np.mean([metric.precision for metric in per_class.values()])),
        float(np.mean([metric.recall for metric in per_class.values()])),
        float(np.mean([metric.f1 for metric in per_class.values()])),
    )


def predict_with_unknown(
    probabilities: np.ndarray,
    labels: Sequence[str],
    *,
    confidence_threshold: float,
    unknown_label: str = "UNKNOWN",
) -> list[str]:
    if not 0 <= confidence_threshold <= 1:
        raise ValueError("confidence_threshold must be between 0 and 1")
    if probabilities.ndim != 2 or probabilities.shape[1] != len(labels):
        raise ValueError("probabilities must have shape (samples, labels)")
    if not np.isfinite(probabilities).all():
        raise ValueError("probabilities must be finite")
    if np.any(probabilities < 0) or np.any(probabilities > 1):
        raise ValueError("probabilities must be within [0, 1]")
    winners = probabilities.argmax(axis=1)
    return [
        labels[index] if probabilities[row, index] >= confidence_threshold else unknown_label
        for row, index in enumerate(winners)
    ]


def measure_latency(operation: Callable[[], object], *, iterations: int = 20) -> dict[str, float]:
    """Measure a caller-provided inference operation; values are descriptive only."""
    if iterations < 1:
        raise ValueError("iterations must be positive")
    durations = []
    for _ in range(iterations):
        start = perf_counter()
        operation()
        durations.append((perf_counter() - start) * 1000)
    return {
        "iterations": float(iterations),
        "mean_ms": float(np.mean(durations)),
        "median_ms": float(np.median(durations)),
        "p95_ms": float(np.percentile(durations, 95)),
    }
