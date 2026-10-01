"""Adapter contract for future supported landmark extraction integrations."""

from typing import Protocol

import numpy as np


class LandmarkExtractor(Protocol):
    """Convert one caller-owned frame into 543 ordered xyz landmarks.

    Implementations must be backed by a demonstrated supported Python API. This
    scaffold intentionally ships no concrete image/video extractor or storage.
    """

    def extract_frame(self, frame: object) -> np.ndarray:
        """Return a numeric ``(543, 3)`` array for pose, face, and both hands."""
