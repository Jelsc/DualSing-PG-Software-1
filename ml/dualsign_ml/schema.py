"""Versioned landmark feature boundary shared by ingestion, training, and export."""

from dataclasses import dataclass

import numpy as np

from dualsign_ml import SCHEMA_VERSION


@dataclass(frozen=True)
class LandmarkSchema:
    version: str = SCHEMA_VERSION
    feature_count: int = 1629
    normalization: str = "per-frame z-score; zero-variance dimensions map to zero"

    def validate(self, sequences: np.ndarray) -> None:
        if sequences.ndim != 3:
            raise ValueError("sequences must have shape (samples, sequence, features)")
        if sequences.shape[0] == 0 or sequences.shape[1] == 0:
            raise ValueError("sequences and sequence lengths must be non-empty")
        if sequences.shape[2] != self.feature_count:
            raise ValueError(f"expected {self.feature_count} features, got {sequences.shape[2]}")
        if not np.issubdtype(sequences.dtype, np.number):
            raise ValueError("landmark features must be numeric")
        if not np.isfinite(sequences).all():
            raise ValueError("landmark features must be finite")

    def normalize(self, sequences: np.ndarray, lengths: np.ndarray) -> np.ndarray:
        self.validate(sequences)
        if lengths.shape != (sequences.shape[0],):
            raise ValueError("lengths must contain one value per sample")
        if np.any(lengths < 1) or np.any(lengths > sequences.shape[1]):
            raise ValueError("sequence lengths must be within the padded sequence dimensions")

        output = np.zeros(sequences.shape, dtype=np.float32)
        for index, length in enumerate(lengths):
            frames = sequences[index, : int(length)].astype(np.float32, copy=False)
            mean = frames.mean(axis=0, keepdims=True)
            std = frames.std(axis=0, keepdims=True)
            output[index, : int(length)] = np.divide(
                frames - mean,
                std,
                out=np.zeros_like(frames),
                where=std > 0,
            )
        return output
