"""Consent-gated loading and participant-grouped partitioning of numeric sequences."""

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from dualsign_ml.schema import LandmarkSchema


@dataclass(frozen=True)
class SequenceDataset:
    features: np.ndarray
    lengths: np.ndarray
    participant_ids: tuple[str, ...]
    sign_ids: tuple[str, ...]
    audit_refs: tuple[str, ...]

    def __len__(self) -> int:
        return len(self.sign_ids)


@dataclass(frozen=True)
class DatasetSplit:
    train: np.ndarray
    validation: np.ndarray
    test: np.ndarray


def load_npz_dataset(
    path: str | Path,
    *,
    validated_sign_ids: set[str],
    schema: LandmarkSchema = LandmarkSchema(),
) -> SequenceDataset:
    """Load an NPZ numeric-only manifest. No video or personal identity is accepted."""
    with np.load(path, allow_pickle=False) as archive:
        required = {
            "features",
            "lengths",
            "participant_ids",
            "sign_ids",
            "consent_granted",
            "audit_refs",
            "schema_version",
        }
        if set(archive.files) != required:
            raise ValueError(f"dataset arrays must be exactly: {', '.join(sorted(required))}")
        features = archive["features"]
        lengths = archive["lengths"].astype(np.int64, copy=False)
        participant_ids = _string_array(archive["participant_ids"], "participant_ids")
        sign_ids = _string_array(archive["sign_ids"], "sign_ids")
        consent = archive["consent_granted"]
        audit_refs = _string_array(archive["audit_refs"], "audit_refs")
        schema_version = _string_array(archive["schema_version"], "schema_version")

    sample_count = features.shape[0] if features.ndim else 0
    for name, values in (
        ("lengths", lengths),
        ("participant_ids", participant_ids),
        ("sign_ids", sign_ids),
        ("consent_granted", consent),
        ("audit_refs", audit_refs),
    ):
        if values.shape != (sample_count,):
            raise ValueError(f"{name} must contain one value per sample")
    if schema_version.shape != (1,) or schema_version[0] != schema.version:
        raise ValueError(f"dataset schema must be {schema.version}")
    if consent.dtype != np.bool_ or not consent.all():
        raise ValueError("every sample requires recorded consent")
    if any(not value.startswith("participant_") for value in participant_ids):
        raise ValueError("participant identifiers must be pseudonymous participant_* values")
    if any(not value for value in audit_refs):
        raise ValueError("every sample requires a non-empty opaque consent audit reference")
    unknown = set(sign_ids) - validated_sign_ids
    if unknown:
        raise ValueError("dataset contains sign IDs absent from the validated catalog")
    schema.validate(features)
    if np.any(lengths < 1) or np.any(lengths > features.shape[1]):
        raise ValueError("sequence lengths must be within the padded sequence dimensions")

    normalized = schema.normalize(features, lengths)
    return SequenceDataset(
        normalized,
        lengths,
        tuple(participant_ids.tolist()),
        tuple(sign_ids.tolist()),
        tuple(audit_refs.tolist()),
    )


def split_by_participant(
    participant_ids: tuple[str, ...],
    *,
    seed: int,
    validation_fraction: float = 0.2,
    test_fraction: float = 0.2,
) -> DatasetSplit:
    """Assign whole participants to splits; requires at least three participants."""
    if validation_fraction <= 0 or test_fraction <= 0:
        raise ValueError("validation and test fractions must be positive")
    if validation_fraction + test_fraction >= 1:
        raise ValueError("validation and test fractions must sum to less than one")
    participants = np.asarray(sorted(set(participant_ids)), dtype=str)
    if len(participants) < 3:
        raise ValueError("at least three participants are required for leakage-safe splits")
    shuffled = np.random.default_rng(seed).permutation(participants)
    validation_count = max(1, round(len(shuffled) * validation_fraction))
    test_count = max(1, round(len(shuffled) * test_fraction))
    while validation_count + test_count >= len(shuffled):
        if validation_count >= test_count:
            validation_count -= 1
        else:
            test_count -= 1
    validation_people = set(shuffled[:validation_count])
    test_people = set(shuffled[validation_count : validation_count + test_count])
    held_out = validation_people | test_people
    train = np.array([i for i, person in enumerate(participant_ids) if person not in held_out])
    validation = np.array(
        [i for i, person in enumerate(participant_ids) if person in validation_people]
    )
    test = np.array([i for i, person in enumerate(participant_ids) if person in test_people])
    return DatasetSplit(train, validation, test)


def _string_array(value: np.ndarray, name: str) -> np.ndarray:
    if value.dtype.kind not in {"U", "S"}:
        raise ValueError(f"{name} must use non-object string arrays")
    return value.astype(str)
