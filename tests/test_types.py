"""Task 01 tests: enumerations and math utilities."""

import pytest

from chan_core.common.math_utils import overlap, strict_overlap
from chan_core.common.types import Direction, FractalType, SegmentState, TrendType


# ═══════════════════════════════════════════════════════════
#  Enumerations
# ═══════════════════════════════════════════════════════════


def test_direction_members() -> None:
    assert Direction.UP.value == "UP"
    assert Direction.DOWN.value == "DOWN"
    assert len(Direction) == 2


def test_fractal_type_members() -> None:
    assert FractalType.TOP.value == "TOP"
    assert FractalType.BOT.value == "BOT"
    assert len(FractalType) == 2


def test_segment_state_members() -> None:
    assert SegmentState.BUILDING.value == "BUILDING"
    assert SegmentState.CONFIRMED.value == "CONFIRMED"
    assert len(SegmentState) == 2


def test_trend_type_members() -> None:
    assert TrendType.CONSOLIDATION.value == "CONSOLIDATION"
    assert TrendType.UP_TREND.value == "UP_TREND"
    assert TrendType.DOWN_TREND.value == "DOWN_TREND"
    assert len(TrendType) == 3


# ═══════════════════════════════════════════════════════════
#  overlap()
# ═══════════════════════════════════════════════════════════


# ── Positive ──────────────────────────────────────────────


def test_overlap_partial() -> None:
    assert overlap(1, 3, 2, 4) is True


def test_overlap_contained() -> None:
    assert overlap(1, 4, 2, 3) is True


def test_overlap_same_interval() -> None:
    assert overlap(1, 3, 1, 3) is True


# ── Negative ──────────────────────────────────────────────


def test_overlap_disjoint() -> None:
    assert overlap(1, 2, 3, 4) is False


def test_overlap_disjoint_reversed() -> None:
    assert overlap(3, 4, 1, 2) is False


# ── Boundary ──────────────────────────────────────────────


def test_overlap_touching_endpoint() -> None:
    """Closed interval: endpoints touching → overlap."""
    assert overlap(1, 2, 2, 3) is True


def test_overlap_zero_length_same_point() -> None:
    """[2,2] ∩ [2,2] = {2} → overlap."""
    assert overlap(2, 2, 2, 2) is True


def test_overlap_zero_length_different_point() -> None:
    """[1,1] ∩ [2,2] = ∅."""
    assert overlap(1, 1, 2, 2) is False


def test_overlap_zero_length_touching() -> None:
    """[1,1] ∩ [1,2] = {1}."""
    assert overlap(1, 1, 1, 2) is True


# ── Extreme ───────────────────────────────────────────────


def test_overlap_very_large() -> None:
    assert overlap(0, 1e15, 5e14, 2e15) is True


def test_overlap_very_small_gap() -> None:
    assert overlap(1.0, 2.0, 2.0 + 1e-15, 3.0) is False


# ═══════════════════════════════════════════════════════════
#  strict_overlap()
# ═══════════════════════════════════════════════════════════


# ── Positive ──────────────────────────────────────────────


def test_strict_overlap_partial() -> None:
    assert strict_overlap(1, 3, 2, 4) is True


def test_strict_overlap_contained() -> None:
    assert strict_overlap(1, 4, 2, 3) is True


# ── Negative ──────────────────────────────────────────────


def test_strict_overlap_disjoint() -> None:
    assert strict_overlap(1, 2, 3, 4) is False


# ── Boundary ──────────────────────────────────────────────


def test_strict_overlap_touching_endpoint() -> None:
    """Strict: endpoints touching → NO overlap."""
    assert strict_overlap(1, 2, 2, 3) is False


def test_strict_overlap_zero_length_same() -> None:
    """[2,2] strict_overlap [2,2] → False (max=2 < min=2 is False)."""
    assert strict_overlap(2, 2, 2, 2) is False


def test_strict_overlap_zero_length_inside() -> None:
    """[2,2] strict_overlap [1,3] → False (point has no interior)."""
    assert strict_overlap(2, 2, 1, 3) is False


# ── Extreme ───────────────────────────────────────────────


def test_strict_overlap_very_large() -> None:
    assert strict_overlap(0, 1e15, 5e14, 2e15) is True


def test_strict_overlap_barely() -> None:
    """Intervals overlap by a tiny amount."""
    assert strict_overlap(1.0, 2.0 + 1e-10, 2.0, 3.0) is True
