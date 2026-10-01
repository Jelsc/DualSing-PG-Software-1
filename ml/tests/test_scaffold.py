from pathlib import Path

import numpy as np
import onnx
import pytest
import torch

from dualsign_ml.data import load_npz_dataset, split_by_participant
from dualsign_ml.evaluation import classification_metrics, measure_latency, predict_with_unknown
from dualsign_ml.export import check_onnx_parity, export_onnx
from dualsign_ml.model import LandmarkGRU
from dualsign_ml.schema import LandmarkSchema
from dualsign_ml.training import TrainingConfig, train_gru


def _write_dataset(path: Path, *, consent: bool = True, sign_id: str = "test-class-a") -> None:
    np.savez(
        path,
        features=np.arange(3 * 4 * 6, dtype=np.float32).reshape(3, 4, 6),
        lengths=np.array([4, 3, 2]),
        participant_ids=np.array(["participant_a", "participant_b", "participant_c"]),
        sign_ids=np.array([sign_id, "test-class-b", "test-class-a"]),
        consent_granted=np.array([consent, True, True]),
        audit_refs=np.array(["audit_ref_a", "audit_ref_b", "audit_ref_c"]),
        schema_version=np.array(["dualsign-landmarks-v1"]),
    )


def test_loader_requires_consent_validated_ids_and_versioned_numeric_features(
    tmp_path: Path,
) -> None:
    dataset_path = tmp_path / "synthetic.npz"
    _write_dataset(dataset_path)
    dataset = load_npz_dataset(
        dataset_path,
        validated_sign_ids={"test-class-a", "test-class-b"},
        schema=LandmarkSchema(feature_count=6),
    )
    assert dataset.features.shape == (3, 4, 6)
    assert dataset.audit_refs[0] == "audit_ref_a"
    with pytest.raises(ValueError, match="validated catalog"):
        load_npz_dataset(
            dataset_path,
            validated_sign_ids={"test-class-b"},
            schema=LandmarkSchema(feature_count=6),
        )

    _write_dataset(dataset_path, consent=False)
    with pytest.raises(ValueError, match="consent"):
        load_npz_dataset(
            dataset_path,
            validated_sign_ids={"test-class-a", "test-class-b"},
            schema=LandmarkSchema(feature_count=6),
        )


def test_normalization_and_participant_split_are_deterministic_and_disjoint() -> None:
    schema = LandmarkSchema(feature_count=2)
    raw = np.array([[[1, 4], [3, 4], [99, 99]]], dtype=np.float32)
    normalized = schema.normalize(raw, np.array([2]))
    np.testing.assert_allclose(normalized[0, :2, 0], [-1, 1])
    np.testing.assert_array_equal(normalized[0, :, 1], [0, 0, 0])

    participants = ("p1", "p1", "p2", "p3", "p4", "p5", "p5")
    first = split_by_participant(participants, seed=7)
    second = split_by_participant(participants, seed=7)
    np.testing.assert_array_equal(first.train, second.train)
    participant_sets = [
        {participants[index] for index in split}
        for split in (first.train, first.validation, first.test)
    ]
    assert all(
        not left & right
        for i, left in enumerate(participant_sets)
        for right in participant_sets[i + 1 :]
    )
    with pytest.raises(ValueError, match="three participants"):
        split_by_participant(("p1", "p2"), seed=0)


def test_metrics_unknown_policy_latency_and_short_cpu_training() -> None:
    metrics = classification_metrics(
        ["test-class-a", "test-class-b", "test-class-a"],
        ["test-class-a", "test-class-a", "test-class-a"],
        ["test-class-a", "test-class-b"],
    )
    assert metrics.confusion_matrix == ((2, 0), (1, 0))
    assert metrics.per_class["test-class-a"].precision == pytest.approx(2 / 3)
    assert metrics.per_class["test-class-b"].recall == 0

    predictions = predict_with_unknown(
        np.array([[0.8, 0.2], [0.6, 0.4]]),
        ["test-class-a", "test-class-b"],
        confidence_threshold=0.7,
    )
    assert predictions == ["test-class-a", "UNKNOWN"]
    latency = measure_latency(lambda: None, iterations=3)
    assert latency["iterations"] == 3
    assert latency["p95_ms"] >= 0

    features = np.random.default_rng(2).normal(size=(4, 3, 6)).astype(np.float32)
    model, history = train_gru(
        features,
        np.array([3, 2, 3, 1]),
        ["test-class-a", "test-class-b", "test-class-a", "test-class-b"],
        class_names=["test-class-a", "test-class-b"],
        config=TrainingConfig(epochs=2, batch_size=2, hidden_size=4, seed=2),
    )
    assert isinstance(model, LandmarkGRU)
    assert len(history) == 2
    assert all(np.isfinite(history))
    assert torch.get_num_threads() == 1


def test_onnx_export_has_dynamic_batch_and_sequence_with_cpu_parity(tmp_path: Path) -> None:
    torch.manual_seed(1)
    model = LandmarkGRU(feature_count=6, class_count=2, hidden_size=4).eval()
    destination = export_onnx(model, tmp_path / "baseline.onnx", example_sequence_length=4)
    max_difference = check_onnx_parity(
        model,
        destination,
        sample_shapes=((2, 4), (1, 2), (3, 6)),
    )
    graph = onnx.load(destination)
    graph_inputs = {value.name: value for value in graph.graph.input}
    sequence_dims = graph_inputs["sequences"].type.tensor_type.shape.dim
    length_dims = graph_inputs["lengths"].type.tensor_type.shape.dim
    assert sequence_dims[0].dim_param == "batch"
    assert sequence_dims[1].dim_param == "sequence"
    assert sequence_dims[2].dim_value == 6
    assert length_dims[0].dim_param == "batch"
    assert destination.is_file()
    assert max_difference < 1e-4
