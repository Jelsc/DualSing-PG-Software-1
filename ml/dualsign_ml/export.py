"""ONNX export and CPU-runtime parity checks for the GRU baseline."""

from pathlib import Path

import numpy as np
import onnx
import onnxruntime as ort
import torch

from dualsign_ml.model import LandmarkGRU


def export_onnx(
    model: LandmarkGRU,
    destination: str | Path,
    *,
    example_sequence_length: int = 5,
) -> Path:
    if example_sequence_length < 1:
        raise ValueError("example_sequence_length must be positive")
    model = model.cpu().eval()
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    features = next(model.parameters()).shape[1]
    dummy_sequences = torch.zeros(1, example_sequence_length, features, dtype=torch.float32)
    dummy_lengths = torch.full((1,), example_sequence_length, dtype=torch.int64)
    torch.onnx.export(
        model,
        (dummy_sequences, dummy_lengths),
        destination,
        input_names=["sequences", "lengths"],
        output_names=["logits"],
        dynamo=False,
        dynamic_axes={
            "sequences": {0: "batch", 1: "sequence"},
            "lengths": {0: "batch"},
            "logits": {0: "batch"},
        },
        opset_version=17,
    )
    onnx_model = onnx.load(destination)
    onnx.checker.check_model(onnx_model)
    graph_inputs = {value.name: value for value in onnx_model.graph.input}
    if set(graph_inputs) != {"sequences", "lengths"}:
        raise ValueError("exported ONNX graph has unexpected inputs")
    sequence_dims = graph_inputs["sequences"].type.tensor_type.shape.dim
    length_dims = graph_inputs["lengths"].type.tensor_type.shape.dim
    if (
        sequence_dims[0].dim_param != "batch"
        or sequence_dims[1].dim_param != "sequence"
        or sequence_dims[2].dim_value != features
        or length_dims[0].dim_param != "batch"
    ):
        raise ValueError("exported ONNX graph does not preserve dynamic batch/sequence inputs")
    return destination


def check_onnx_parity(
    model: LandmarkGRU,
    model_path: str | Path,
    *,
    sample_shapes: tuple[tuple[int, int], ...] = ((2, 5), (1, 3)),
    rtol: float = 1e-4,
    atol: float = 1e-5,
) -> float:
    session = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
    model = model.cpu().eval()
    max_difference = 0.0
    generator = np.random.default_rng(0)
    features = next(model.parameters()).shape[1]
    for batch_size, sequence_length in sample_shapes:
        if batch_size < 1 or sequence_length < 1:
            raise ValueError("parity sample dimensions must be positive")
        input_array = generator.normal(size=(batch_size, sequence_length, features)).astype(
            np.float32
        )
        lengths_array = np.full(batch_size, sequence_length, dtype=np.int64)
        with torch.inference_mode():
            expected = model(torch.from_numpy(input_array), torch.from_numpy(lengths_array)).numpy()
        actual = session.run(["logits"], {"sequences": input_array, "lengths": lengths_array})[0]
        np.testing.assert_allclose(actual, expected, rtol=rtol, atol=atol)
        max_difference = max(max_difference, float(np.max(np.abs(actual - expected))))
    return max_difference
