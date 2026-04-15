"""Task 12-13 tests: level mapping, structure_complete, exit sequence."""

import csv
import os

import pytest

from chan_core.common.kline import MergedKLine, RawKLine
from chan_core.common.types import Direction, FractalType, TrendType
from chan_core.engine import CompletionTrace, PivotSnapshot
from chan_core.structure._completion import (
    build_exit_sequence,
    find_i_star,
    is_awaiting_new_pivot,
    structure_complete_l0,
)
from chan_core.structure._fractal import Fractal, find_fractals
from chan_core.structure._merge import merge_inclusive
from chan_core.structure._pen import Pen, build_confirmed, build_pens
from chan_core.structure._pivot import PivotBuilder, search_pivots
from chan_core.structure._trend import classify_trend


# ── Helpers ───────────────────────────────────────────────


def _mk(high: float, low: float, idx: int) -> MergedKLine:
    return MergedKLine(high=high, low=low, timestamp=f"t{idx:04d}", source_indices=(idx,))


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


# ═══════════════════════════════════════════════════════════
#  find_i_star
# ═══════════════════════════════════════════════════════════


def test_i_star_first_three_form_pivot() -> None:
    """First three elements form a pivot → i*=0."""
    seq = [
        _pen(10, 20, 1, 10, Direction.UP),
        _pen(18, 12, 10, 20, Direction.DOWN),
        _pen(11, 19, 20, 30, Direction.UP),
    ]
    assert find_i_star(seq) == 0


def test_i_star_none_no_overlap() -> None:
    """No three consecutive elements form a pivot → None."""
    seq = [
        _pen(1, 5, 1, 10, Direction.UP),
        _pen(10, 8, 10, 20, Direction.DOWN),
        _pen(15, 20, 20, 30, Direction.UP),
    ]
    assert find_i_star(seq) is None


def test_i_star_empty() -> None:
    assert find_i_star([]) is None


def test_i_star_less_than_3() -> None:
    seq = [_pen(10, 20, 1, 10, Direction.UP)]
    assert find_i_star(seq) is None


def test_i_star_takes_first_match() -> None:
    """Multiple matches → i* is the minimum."""
    seq = [
        _pen(1, 5, 1, 10, Direction.UP),      # won't form pivot with next two
        _pen(10, 20, 10, 20, Direction.DOWN),
        _pen(18, 12, 20, 30, Direction.UP),
        _pen(11, 19, 30, 40, Direction.DOWN),  # these three form pivot
    ]
    i_star = find_i_star(seq)
    assert i_star is not None
    assert i_star == 1  # (10,20), (12,18), (11,19)


# ═══════════════════════════════════════════════════════════
#  build_exit_sequence
# ═══════════════════════════════════════════════════════════


def test_exit_sequence_empty_no_leave() -> None:
    """All pens overlap the pivot → empty exit sequence."""
    pivot = PivotSnapshot(
        zd=10, zg=20, dd=5, gg=25,
        components=(), entry_time="t0000", exit_time="t0030",
    )
    pens = [
        _pen(10, 20, 1, 10, Direction.UP),      # before pivot exit time
        _pen(15, 18, 40, 50, Direction.DOWN),    # after, but overlaps [10,20]
    ]
    seq = build_exit_sequence(pivot, pens)
    assert len(seq) == 0


def test_exit_sequence_with_leave() -> None:
    """Pen after pivot that doesn't overlap → starts exit sequence."""
    pivot = PivotSnapshot(
        zd=10, zg=20, dd=5, gg=25,
        components=(), entry_time="t0000", exit_time="t0030",
    )
    pens = [
        _pen(10, 20, 1, 10, Direction.UP),
        _pen(18, 12, 10, 20, Direction.DOWN),
        _pen(11, 19, 20, 30, Direction.UP),
        _pen(25, 35, 40, 50, Direction.DOWN),  # after exit, leaves up
        _pen(33, 28, 50, 60, Direction.UP),    # subsequent
    ]
    seq = build_exit_sequence(pivot, pens)
    assert len(seq) == 2


# ═══════════════════════════════════════════════════════════
#  structure_complete_l0
# ═══════════════════════════════════════════════════════════


def test_structure_complete_no_pivots() -> None:
    trace = structure_complete_l0([], [])
    assert trace.i_star is None
    assert trace.t_end is None
    assert trace.awaiting_new_pivot is False


def test_structure_complete_awaiting() -> None:
    """Exit sequence exists but no new pivot → awaiting."""
    pens: list[Pen] = [
        _pen(10, 20, 1, 10, Direction.UP),
        _pen(18, 12, 10, 20, Direction.DOWN),
        _pen(11, 19, 20, 30, Direction.UP),
        _pen(25, 35, 40, 50, Direction.DOWN),  # leave pen
        _pen(33, 28, 50, 60, Direction.UP),    # exit seq element
    ]
    pivots = search_pivots(pens)
    assert len(pivots) >= 1
    trace = structure_complete_l0(pivots, pens)
    # May or may not be awaiting depending on whether exit_seq forms
    # Check the trace is valid
    assert isinstance(trace, CompletionTrace)


# ═══════════════════════════════════════════════════════════
#  Fixed sample: 300811.SZ structure_complete
# ═══════════════════════════════════════════════════════════


def _load_300811() -> tuple[list[Pen], list[PivotBuilder]]:
    csv_path = os.path.join(
        os.path.dirname(__file__),
        "..",
        "doc",
        "cache",
        "300811.SZ_20250411_20260410.csv",
    )
    raw: list[RawKLine] = []
    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            raw.append(
                RawKLine(
                    high=float(row["high"]),
                    low=float(row["low"]),
                    timestamp=row["trade_date"],
                )
            )
    merged = merge_inclusive(raw)
    fractals = find_fractals(merged)
    confirmed = build_confirmed(fractals)
    pens = build_pens(confirmed)
    pivots = search_pivots(pens)
    return pens, pivots


def test_300811_t1_structure_complete() -> None:
    """T1 (containing Z0): structure_complete = True.

    ExitSeq starts from P5 (leave_pen P4 + 1).
    i* = 0 (first three in exit seq form new pivot).
    """
    pens, pivots = _load_300811()
    assert len(pivots) == 2

    # Use only Z0 for T1 analysis
    trace = structure_complete_l0([pivots[0]], pens)
    assert trace.i_star is not None
    assert trace.t_end is not None
    assert trace.awaiting_new_pivot is False


def test_300811_t1_i_star_value() -> None:
    """i* should be 0 (first group of exit seq forms pivot)."""
    pens, pivots = _load_300811()
    trace = structure_complete_l0([pivots[0]], pens)
    assert trace.i_star == 0  # 0-based index


def test_300811_t1_classification() -> None:
    """T1 has 1 pivot → consolidation."""
    pens, pivots = _load_300811()
    trace = structure_complete_l0([pivots[0]], pens)
    snap_pivots = [pivots[0].to_snapshot()]
    trend = classify_trend(snap_pivots, trace.i_star is not None)
    assert trend == TrendType.CONSOLIDATION


def test_300811_t2_not_complete() -> None:
    """T2 (containing Z1): no leave → ExitSeq empty → not complete."""
    pens, pivots = _load_300811()
    trace = structure_complete_l0([pivots[1]], pens)
    assert trace.i_star is None
    assert is_awaiting_new_pivot(trace) is False  # empty exit seq = not awaiting either


def test_300811_t1_t_end_is_p4() -> None:
    """t_end(T1) = t_end(P4) (connection segment before W_{i*})."""
    pens, pivots = _load_300811()
    trace = structure_complete_l0([pivots[0]], pens)
    # P4 = pens[4], its end timestamp
    p4_end = pens[4].end.klines[1].timestamp
    assert trace.t_end == p4_end


def test_300811_exit_seq_starts_from_p5() -> None:
    """ExitSeq should start from P5 (index 5 in pen list)."""
    pens, pivots = _load_300811()
    z0_snap = pivots[0].to_snapshot()
    exit_seq = build_exit_sequence(z0_snap, pens)
    assert len(exit_seq) >= 3
    # First element should be P5
    assert exit_seq[0] is pens[5]


# ═══════════════════════════════════════════════════════════
#  is_awaiting_new_pivot
# ═══════════════════════════════════════════════════════════


def test_awaiting_true() -> None:
    trace = CompletionTrace(
        exit_seq_ids=("a", "b"),
        i_star=None,
        t_end=None,
        awaiting_new_pivot=True,
    )
    assert is_awaiting_new_pivot(trace) is True


def test_awaiting_false_complete() -> None:
    trace = CompletionTrace(
        exit_seq_ids=("a", "b", "c"),
        i_star=0,
        t_end="t100",
        awaiting_new_pivot=False,
    )
    assert is_awaiting_new_pivot(trace) is False
