"""Heuristic confidence and uncertainty model for evidence-driven decisions."""

from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar


class ConfidenceLevel(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    SPECULATIVE = "speculative"
    INSUFFICIENT = "insufficient"  # Athena declines to classify


@dataclass(frozen=True, slots=True)
class Confidence:
    """A heuristic confidence score paired with its qualitative level.

    IMPORTANT: this is a heuristic weighting of deterministic evidence
    rules, NOT a calibrated statistical probability. ``score=0.97`` means
    "given the current evidence-weighting rules, this interpretation is
    highly supported" — it does NOT mean "97% probability of being
    correct." Calibration against real outcomes is future evaluation work,
    not part of this ADR.
    """

    score: float  # 0.0 - 1.0, heuristic weight — not a probability
    level: ConfidenceLevel

    _HIGH_THRESHOLD: ClassVar[float] = 0.85
    _MEDIUM_THRESHOLD: ClassVar[float] = 0.60
    _LOW_THRESHOLD: ClassVar[float] = 0.35

    @staticmethod
    def from_score(score: float) -> "Confidence":
        if not 0.0 <= score <= 1.0:
            raise ValueError("Confidence score must be within [0.0, 1.0]")
        if score >= Confidence._HIGH_THRESHOLD:
            level = ConfidenceLevel.HIGH
        elif score >= Confidence._MEDIUM_THRESHOLD:
            level = ConfidenceLevel.MEDIUM
        elif score >= Confidence._LOW_THRESHOLD:
            level = ConfidenceLevel.LOW
        else:
            level = ConfidenceLevel.SPECULATIVE
        return Confidence(score=score, level=level)

    @staticmethod
    def insufficient() -> "Confidence":
        """'Athena declines to classify' — distinct from a low numeric score."""
        return Confidence(score=0.0, level=ConfidenceLevel.INSUFFICIENT)
