"""Tests for the heuristic Confidence and ConfidenceLevel model."""

import pytest

from packages.domains.evidence.confidence import Confidence, ConfidenceLevel


def test_confidence_level_has_expected_variants() -> None:
    """All five confidence levels must be present per the ADR."""
    assert ConfidenceLevel.HIGH.value == "high"
    assert ConfidenceLevel.MEDIUM.value == "medium"
    assert ConfidenceLevel.LOW.value == "low"
    assert ConfidenceLevel.SPECULATIVE.value == "speculative"
    assert ConfidenceLevel.INSUFFICIENT.value == "insufficient"


@pytest.mark.parametrize(
    ("score", "expected_level"),
    [
        (0.85, ConfidenceLevel.HIGH),
        (1.0, ConfidenceLevel.HIGH),
        (0.86, ConfidenceLevel.HIGH),
    ],
)
def test_from_score_maps_high_threshold(
    score: float, expected_level: ConfidenceLevel
) -> None:
    """Scores at or above 0.85 are HIGH."""
    confidence = Confidence.from_score(score)
    assert confidence.score == score
    assert confidence.level == expected_level


@pytest.mark.parametrize(
    ("score", "expected_level"),
    [
        (0.60, ConfidenceLevel.MEDIUM),
        (0.84, ConfidenceLevel.MEDIUM),
    ],
)
def test_from_score_maps_medium_threshold(
    score: float, expected_level: ConfidenceLevel
) -> None:
    """Scores at 0.60 up to (but not including) 0.85 are MEDIUM."""
    confidence = Confidence.from_score(score)
    assert confidence.score == score
    assert confidence.level == expected_level


@pytest.mark.parametrize(
    ("score", "expected_level"),
    [
        (0.35, ConfidenceLevel.LOW),
        (0.59, ConfidenceLevel.LOW),
    ],
)
def test_from_score_maps_low_threshold(
    score: float, expected_level: ConfidenceLevel
) -> None:
    """Scores at 0.35 up to (but not including) 0.60 are LOW."""
    confidence = Confidence.from_score(score)
    assert confidence.score == score
    assert confidence.level == expected_level


@pytest.mark.parametrize(
    ("score", "expected_level"),
    [
        (0.0, ConfidenceLevel.SPECULATIVE),
        (0.10, ConfidenceLevel.SPECULATIVE),
        (0.34, ConfidenceLevel.SPECULATIVE),
    ],
)
def test_from_score_maps_speculative_threshold(
    score: float, expected_level: ConfidenceLevel
) -> None:
    """Scores below 0.35 (but non-negative) are SPECULATIVE, not INSUFFICIENT."""
    confidence = Confidence.from_score(score)
    assert confidence.score == score
    assert confidence.level == expected_level


@pytest.mark.parametrize("score", [-0.01, -1.0, 1.01, 2.0])
def test_from_score_raises_outside_valid_range(score: float) -> None:
    """Scores outside [0.0, 1.0] must raise ValueError."""
    with pytest.raises(ValueError, match="Confidence score must be within"):
        Confidence.from_score(score)


def test_insufficient_returns_insufficient_level() -> None:
    """insufficient() must always produce the INSUFFICIENT level."""
    confidence = Confidence.insufficient()
    assert confidence.level == ConfidenceLevel.INSUFFICIENT
    assert confidence.score == 0.0


def test_insufficient_is_distinct_from_speculative() -> None:
    """INSUFFICIENT must not collapse into a numeric level like SPECULATIVE."""
    insufficient = Confidence.insufficient()
    speculative = Confidence.from_score(0.0)

    assert insufficient.level != speculative.level
    assert insufficient.level == ConfidenceLevel.INSUFFICIENT
    assert speculative.level == ConfidenceLevel.SPECULATIVE
