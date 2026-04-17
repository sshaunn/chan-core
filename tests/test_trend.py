"""Task 11 tests: trend classifier."""

import pytest

from chan_core.common.types import TrendType
from chan_core.engine import PivotSnapshot
from chan_core.structure._trend import classify_trend


def _pivot(zd: float, zg: float, dd: float, gg: float) -> PivotSnapshot:
    return PivotSnapshot(
        zd=zd, zg=zg, dd=dd, gg=gg,
        components=(), entry_time="t0", exit_time="t1",
    )


# ── Positive ──────────────────────────────────────────────


def test_consolidation_one_pivot() -> None:
    pivots = [_pivot(10, 20, 5, 25)]
    assert classify_trend(pivots, True) == TrendType.CONSOLIDATION


def test_up_trend_two_pivots() -> None:
    """ZD2 > ZG1 → up trend (§3.2 core interval)."""
    pivots = [_pivot(10, 20, 5, 25), _pivot(30, 40, 26, 45)]
    assert classify_trend(pivots, True) == TrendType.UP_TREND


def test_down_trend_two_pivots() -> None:
    """ZG2 < ZD1 → down trend (§3.2 core interval)."""
    pivots = [_pivot(30, 40, 25, 45), _pivot(10, 20, 5, 24)]
    assert classify_trend(pivots, True) == TrendType.DOWN_TREND


def test_up_trend_five_pivots() -> None:
    pivots = [_pivot(i * 10, i * 10 + 5, i * 10 - 2, i * 10 + 7) for i in range(5)]
    # ZD[k+1] = (k+1)*10, ZG[k] = k*10+5
    # Need ZD[k+1] > ZG[k]: (k+1)*10 > k*10+5 → 10 > 5 ✓
    assert classify_trend(pivots, True) == TrendType.UP_TREND


# ── Negative ──────────────────────────────────────────────


def test_not_complete_returns_none() -> None:
    pivots = [_pivot(10, 20, 5, 25)]
    assert classify_trend(pivots, False) is None


def test_no_pivots_returns_none() -> None:
    assert classify_trend([], True) is None


def test_two_pivots_overlapping() -> None:
    """Neither up nor down → None."""
    pivots = [_pivot(10, 20, 5, 25), _pivot(15, 25, 10, 30)]
    assert classify_trend(pivots, True) is None


# ── Boundary ──────────────────────────────────────────────


def test_up_trend_zd_equals_zg_fails() -> None:
    """ZD2 == ZG1 → strict inequality not met → not up trend."""
    pivots = [_pivot(10, 20, 5, 25), _pivot(20, 40, 15, 45)]
    assert classify_trend(pivots, True) is None


def test_down_trend_zg_equals_zd_fails() -> None:
    """ZG2 == ZD1 → strict inequality not met → not down trend."""
    pivots = [_pivot(20, 40, 15, 45), _pivot(10, 20, 5, 25)]
    assert classify_trend(pivots, True) is None


# ── Extreme ───────────────────────────────────────────────


def test_mixed_pivots_not_trend() -> None:
    """First pair satisfies up, second doesn't → not a trend."""
    pivots = [
        _pivot(10, 20, 5, 25),
        _pivot(30, 40, 26, 45),
        _pivot(15, 25, 10, 30),  # ZD=15 < ZG1=40 → not continuing up
    ]
    assert classify_trend(pivots, True) is None
