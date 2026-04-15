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
    """DD2 > GG1 → up trend."""
    pivots = [_pivot(10, 20, 5, 25), _pivot(30, 40, 26, 45)]
    assert classify_trend(pivots, True) == TrendType.UP_TREND


def test_down_trend_two_pivots() -> None:
    """GG2 < DD1 → down trend."""
    pivots = [_pivot(30, 40, 25, 45), _pivot(10, 20, 5, 24)]
    assert classify_trend(pivots, True) == TrendType.DOWN_TREND


def test_up_trend_five_pivots() -> None:
    pivots = [_pivot(i * 10, i * 10 + 5, i * 10 - 2, i * 10 + 7) for i in range(5)]
    # DD[k+1] = (k+1)*10-2, GG[k] = k*10+7
    # Need DD[k+1] > GG[k]: (k+1)*10-2 > k*10+7 → 10-2 > 7 → 8 > 7 ✓
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


def test_up_trend_dd_equals_gg_fails() -> None:
    """DD2 == GG1 → strict inequality not met → not up trend."""
    pivots = [_pivot(10, 20, 5, 25), _pivot(30, 40, 25, 45)]
    assert classify_trend(pivots, True) is None


def test_down_trend_gg_equals_dd_fails() -> None:
    """GG2 == DD1 → strict inequality not met → not down trend."""
    pivots = [_pivot(30, 40, 25, 45), _pivot(10, 20, 5, 25)]
    assert classify_trend(pivots, True) is None


# ── Extreme ───────────────────────────────────────────────


def test_mixed_pivots_not_trend() -> None:
    """First pair satisfies up, second doesn't → not a trend."""
    pivots = [
        _pivot(10, 20, 5, 25),
        _pivot(30, 40, 26, 45),
        _pivot(15, 25, 10, 30),  # DD=10 < GG1=45
    ]
    assert classify_trend(pivots, True) is None
