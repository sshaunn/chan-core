"""Task 06 tests: segment BUILDING state and SegmentBuilder."""

import pytest

from chan_core.common.kline import MergedKLine
from chan_core.common.types import Direction, FractalType, SegmentState
from chan_core.engine import SegmentSnapshot
from chan_core.structure._fractal import Fractal
from chan_core.structure._pen import Pen
from chan_core.structure._segment import SegmentBuilder, check_first_three_overlap


# ── Helpers ───────────────────────────────────────────────


def _mk(high: float, low: float, idx: int) -> MergedKLine:
    return MergedKLine(high=high, low=low, timestamp=f"t{idx}", source_indices=(idx,))


def _fractal(ft: FractalType, val: float, idx: int) -> Fractal:
    if ft == FractalType.TOP:
        left = _mk(val - 2, val - 4, idx - 1)
        mid = _mk(val, val - 2, idx)
        right = _mk(val - 2, val - 4, idx + 1)
    else:
        left = _mk(val + 4, val + 2, idx - 1)
        mid = _mk(val + 2, val, idx)
        right = _mk(val + 4, val + 2, idx + 1)
    return Fractal(type=ft, value=val, klines=(left, mid, right), index=idx)


def _pen(start_val: float, end_val: float, start_idx: int, end_idx: int,
         direction: Direction) -> Pen:
    if direction == Direction.UP:
        start_f = _fractal(FractalType.BOT, start_val, start_idx)
        end_f = _fractal(FractalType.TOP, end_val, end_idx)
    else:
        start_f = _fractal(FractalType.TOP, start_val, start_idx)
        end_f = _fractal(FractalType.BOT, end_val, end_idx)
    return Pen(start=start_f, end=end_f, direction=direction)


def _make_overlapping_3_pens() -> list[Pen]:
    """3 pens with overlap between pen 0 and pen 2."""
    return [
        _pen(10, 20, 1, 10, Direction.UP),    # [10, 20]
        _pen(20, 15, 10, 20, Direction.DOWN),  # [15, 20]
        _pen(15, 25, 20, 30, Direction.UP),    # [15, 25] — overlaps [10, 20]
    ]


def _make_non_overlapping_3_pens() -> list[Pen]:
    """3 pens where pen 0 and pen 2 do NOT overlap."""
    return [
        _pen(10, 20, 1, 10, Direction.UP),    # [10, 20]
        _pen(20, 5, 10, 20, Direction.DOWN),   # [5, 20]
        _pen(5, 8, 20, 30, Direction.UP),      # [5, 8] — no overlap with [10, 20]
    ]


# ═══════════════════════════════════════════════════════════
#  check_first_three_overlap
# ═══════════════════════════════════════════════════════════


# ── Positive ──────────────────────────────────────────────


def test_first_three_overlap_true() -> None:
    pens = _make_overlapping_3_pens()
    assert check_first_three_overlap(pens) is True


# ── Negative ──────────────────────────────────────────────


def test_first_three_overlap_false() -> None:
    pens = _make_non_overlapping_3_pens()
    assert check_first_three_overlap(pens) is False


# ── Boundary ──────────────────────────────────────────────


def test_first_three_overlap_less_than_3() -> None:
    pens = _make_overlapping_3_pens()[:2]
    assert check_first_three_overlap(pens) is False


def test_first_three_overlap_empty() -> None:
    assert check_first_three_overlap([]) is False


def test_first_three_overlap_single() -> None:
    assert check_first_three_overlap([_make_overlapping_3_pens()[0]]) is False


# ═══════════════════════════════════════════════════════════
#  SegmentBuilder basics
# ═══════════════════════════════════════════════════════════


def test_builder_creation() -> None:
    pens = _make_overlapping_3_pens()
    sb = SegmentBuilder(pens=pens, direction=Direction.UP)
    assert sb.state == SegmentState.BUILDING
    assert sb.pen_count == 3
    assert sb.direction == Direction.UP


def test_builder_high_low() -> None:
    pens = _make_overlapping_3_pens()
    sb = SegmentBuilder(pens=pens, direction=Direction.UP)
    assert sb.high == 25  # max of all pen highs
    assert sb.low == 10   # min of all pen lows
    assert sb.interval == (10, 25)


# ═══════════════════════════════════════════════════════════
#  State transitions
# ═══════════════════════════════════════════════════════════


def test_confirm_transition() -> None:
    pens = _make_overlapping_3_pens()
    sb = SegmentBuilder(pens=pens, direction=Direction.UP)
    assert sb.state == SegmentState.BUILDING
    sb.confirm()
    assert sb.state == SegmentState.CONFIRMED


def test_double_confirm_raises() -> None:
    pens = _make_overlapping_3_pens()
    sb = SegmentBuilder(pens=pens, direction=Direction.UP)
    sb.confirm()
    with pytest.raises(RuntimeError, match="already confirmed"):
        sb.confirm()


# ═══════════════════════════════════════════════════════════
#  Snapshot
# ═══════════════════════════════════════════════════════════


def test_snapshot_frozen() -> None:
    pens = _make_overlapping_3_pens()
    sb = SegmentBuilder(pens=pens, direction=Direction.UP)
    snap = sb.to_snapshot()
    assert isinstance(snap, SegmentSnapshot)
    assert snap.state == SegmentState.BUILDING
    assert snap.direction == Direction.UP
    assert snap.high == 25
    assert snap.low == 10
    assert len(snap.pens) == 3

    with pytest.raises(AttributeError):
        snap.high = 100.0  # type: ignore[misc]


def test_snapshot_preserves_confirmed_state() -> None:
    pens = _make_overlapping_3_pens()
    sb = SegmentBuilder(pens=pens, direction=Direction.UP)
    sb.confirm()
    snap = sb.to_snapshot()
    assert snap.state == SegmentState.CONFIRMED


# ═══════════════════════════════════════════════════════════
#  Extreme
# ═══════════════════════════════════════════════════════════


def test_large_segment() -> None:
    """100+ pens in a segment."""
    pens = []
    for i in range(101):
        if i % 2 == 0:
            pens.append(_pen(float(10 + i), float(20 + i), i * 10, i * 10 + 5, Direction.UP))
        else:
            pens.append(_pen(float(20 + i), float(10 + i), i * 10, i * 10 + 5, Direction.DOWN))
    sb = SegmentBuilder(pens=pens, direction=Direction.UP)
    assert sb.pen_count == 101
    snap = sb.to_snapshot()
    assert len(snap.pens) == 101


def test_snapshot_pens_tuple() -> None:
    """Snapshot pens field is a tuple (immutable)."""
    pens = _make_overlapping_3_pens()
    sb = SegmentBuilder(pens=pens, direction=Direction.UP)
    snap = sb.to_snapshot()
    assert isinstance(snap.pens, tuple)
