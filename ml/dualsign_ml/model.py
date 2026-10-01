"""Small CPU-capable GRU baseline for padded landmark sequences."""

import torch
from torch import nn


class LandmarkGRU(nn.Module):
    def __init__(self, feature_count: int, class_count: int, hidden_size: int = 64) -> None:
        super().__init__()
        if min(feature_count, class_count, hidden_size) < 1:
            raise ValueError("feature_count, class_count, and hidden_size must be positive")
        self.gru = nn.GRU(feature_count, hidden_size, batch_first=True)
        self.classifier = nn.Linear(hidden_size, class_count)

    def forward(self, sequences: torch.Tensor, lengths: torch.Tensor) -> torch.Tensor:
        output, _ = self.gru(sequences)
        last_valid = output[
            torch.arange(output.shape[0], device=output.device),
            lengths.to(dtype=torch.long) - 1,
        ]
        return self.classifier(last_valid)
