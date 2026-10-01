"""Deterministic baseline training utilities; callers provide all data and labels."""

import random
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import torch
from torch import nn

from dualsign_ml.model import LandmarkGRU


@dataclass(frozen=True)
class TrainingConfig:
    epochs: int = 5
    batch_size: int = 8
    learning_rate: float = 1e-3
    hidden_size: int = 64
    seed: int = 0


def train_gru(
    features: np.ndarray,
    lengths: np.ndarray,
    labels: Sequence[str],
    *,
    class_names: Sequence[str],
    config: TrainingConfig = TrainingConfig(),
) -> tuple[LandmarkGRU, list[float]]:
    if features.ndim != 3 or lengths.shape != (features.shape[0],) or len(labels) != len(features):
        raise ValueError("features, lengths, and labels have inconsistent shapes")
    if features.shape[0] < 1 or not class_names or len(set(class_names)) != len(class_names):
        raise ValueError("training requires samples and unique class names")
    if set(labels) - set(class_names):
        raise ValueError("every training label must be in class_names")
    if config.epochs < 1 or config.batch_size < 1 or config.learning_rate <= 0:
        raise ValueError("epochs, batch_size, and learning_rate must be positive")
    if np.any(lengths < 1) or np.any(lengths > features.shape[1]):
        raise ValueError("sequence lengths must be within the padded sequence dimensions")

    random.seed(config.seed)
    np.random.seed(config.seed)
    torch.manual_seed(config.seed)
    torch.set_num_threads(1)
    model = LandmarkGRU(features.shape[2], len(class_names), config.hidden_size).cpu()
    optimizer = torch.optim.Adam(model.parameters(), lr=config.learning_rate)
    loss_fn = nn.CrossEntropyLoss()
    class_indices = {label: index for index, label in enumerate(class_names)}
    targets = torch.tensor([class_indices[label] for label in labels], dtype=torch.long)
    inputs = torch.from_numpy(np.asarray(features, dtype=np.float32))
    sequence_lengths = torch.from_numpy(np.asarray(lengths, dtype=np.int64))
    generator = torch.Generator().manual_seed(config.seed)
    history = []
    model.train()
    for _ in range(config.epochs):
        order = torch.randperm(len(labels), generator=generator)
        epoch_loss = 0.0
        for batch in order.split(config.batch_size):
            optimizer.zero_grad(set_to_none=True)
            logits = model(inputs[batch], sequence_lengths[batch])
            loss = loss_fn(logits, targets[batch])
            loss.backward()
            optimizer.step()
            epoch_loss += float(loss.detach()) * len(batch)
        history.append(epoch_loss / len(labels))
    model.eval()
    return model, history
