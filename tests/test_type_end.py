"""Task 08 tests: Type1End, Type2End, t_extreme, build_segments."""

import csv
import os

import pytest

from chan_core.common.kline import MergedKLine, RawKLine
from chan_core.common.types import Direction, FractalType, SegmentState
from chan_core.engine import SegmentSnapshot
from chan_core.structure._fractal import Fractal, find_fractals
from chan_core.structure._feature_sequence import (
    FeatureElement,
    build_feature_sequence,
    check_type1_end,
    check_type2_end,
    find_t_extreme,
    merge_feature_sequence,
)
from chan_core.structure._merge import merge_inclusive
from chan_core.structure._pen import Pen, build_confirmed, build_pens
from chan_core.structure._segment import SegmentBuilder, build_segments


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


def _make_type1_up_segment_pens() -> list[Pen]:
    """UP segment with clear Type1End: overlapping feature sequence fractal.

    UP segment: pen directions UP, DOWN, UP, DOWN, UP
    Feature sequence = DOWN pens (indices 1, 3).
    After merge and adding more pens to get 3+ feature elements, check for top fseq.
    """
    # 7 pens in an UP segment, feature sequence has 3 DOWN pens
    return [
        _pen(10, 20, 1, 10, Direction.UP),     # P0: [10,20]
        _pen(20, 15, 10, 20, Direction.DOWN),   # P1: [15,20] — feat elem 0
        _pen(15, 25, 20, 30, Direction.UP),     # P2: [15,25]
        _pen(25, 18, 30, 40, Direction.DOWN),   # P3: [18,25] — feat elem 1
        _pen(18, 22, 40, 50, Direction.UP),     # P4: [18,22]
        _pen(22, 16, 50, 60, Direction.DOWN),   # P5: [16,22] — feat elem 2
        _pen(16, 24, 60, 70, Direction.UP),     # P6: [16,24]
    ]


# ═══════════════════════════════════════════════════════════
#  check_type1_end
# ═══════════════════════════════════════════════════════════


def test_type1_end_positive() -> None:
    """UP segment with Type1End: feature seq top fractal + overlap → terminates."""
    pens = _make_type1_up_segment_pens()
    result = check_type1_end(pens, Direction.UP)
    # Feature elements: [15,20], [18,25], [16,22]
    # After merge (no inclusion expected): same 3 elements
    # Top fractal at j=1: h=25>20, h=25>22, l=18>15, l=18>16 → YES
    # Overlap [15,20] ∩ [18,25]: max(15,18)=18 ≤ min(20,25)=20 → YES
    # Type1End terminates at h(C'_1) = 25
    assert result is not None
    assert result == 25.0


def test_type1_end_no_fractal() -> None:
    """Only 3 pens → only 1 feature element → no fractal possible."""
    pens = [
        _pen(10, 20, 1, 10, Direction.UP),
        _pen(20, 15, 10, 20, Direction.DOWN),
        _pen(15, 25, 20, 30, Direction.UP),
    ]
    result = check_type1_end(pens, Direction.UP)
    assert result is None  # Only 1 feature element


def test_type1_end_too_few_feature_elements() -> None:
    """Less than 3 feature elements → None."""
    pens = [
        _pen(10, 20, 1, 10, Direction.UP),
        _pen(20, 15, 10, 20, Direction.DOWN),
        _pen(15, 25, 20, 30, Direction.UP),
        _pen(25, 18, 30, 40, Direction.DOWN),
        _pen(18, 30, 40, 50, Direction.UP),
    ]
    # 2 feature elements (DOWN pens) → can't form fractal
    result = check_type1_end(pens, Direction.UP)
    assert result is None


# ═══════════════════════════════════════════════════════════
#  check_type2_end
# ═══════════════════════════════════════════════════════════


def test_type2_end_no_gap_returns_none() -> None:
    """When all feature sequence pairs overlap → no Type2End."""
    pens = _make_type1_up_segment_pens()
    # This already has a Type1End, so Type2End should also check
    # but since there's overlap, Type2End won't trigger at the same position
    result = check_type2_end(pens, Direction.UP)
    assert result is None  # Overlap means Type1End, not Type2End


# ═══════════════════════════════════════════════════════════
#  find_t_extreme
# ═══════════════════════════════════════════════════════════


def test_t_extreme_up_single_pen() -> None:
    p = _pen(10, 20, 1, 10, Direction.UP)
    fe = FeatureElement(high=20, low=10, source_pens=(p,))
    t = find_t_extreme(fe, Direction.UP)
    assert t == p.end.klines[1].timestamp


def test_t_extreme_down_single_pen() -> None:
    p = _pen(20, 10, 1, 10, Direction.DOWN)
    fe = FeatureElement(high=20, low=10, source_pens=(p,))
    t = find_t_extreme(fe, Direction.DOWN)
    assert t == p.end.klines[1].timestamp


def test_t_extreme_tiebreak_earliest() -> None:
    """Multiple pens with same extreme → take earliest t_end."""
    p1 = _pen(10, 20, 1, 10, Direction.UP)    # high=20, t_end=t0010
    p2 = _pen(10, 20, 20, 30, Direction.UP)   # high=20, t_end=t0030
    fe = FeatureElement(high=20, low=10, source_pens=(p1, p2))
    t = find_t_extreme(fe, Direction.UP)
    assert t == p1.end.klines[1].timestamp  # earliest


# ═══════════════════════════════════════════════════════════
#  build_segments — integration
# ═══════════════════════════════════════════════════════════


def test_build_segments_empty() -> None:
    assert build_segments([]) == []


def test_build_segments_less_than_3() -> None:
    pens = [_pen(10, 20, 1, 10, Direction.UP), _pen(20, 15, 10, 20, Direction.DOWN)]
    assert build_segments(pens) == []


def test_build_segments_type1_confirmed() -> None:
    """A segment with clear Type1End should be confirmed."""
    pens = _make_type1_up_segment_pens()
    segments = build_segments(pens)
    assert len(segments) >= 1
    assert segments[0].state == SegmentState.CONFIRMED
    assert segments[0].direction == Direction.UP


def test_build_segments_no_overlap_first_three() -> None:
    """First three pens don't overlap → no segment starts."""
    pens = [
        _pen(10, 20, 1, 10, Direction.UP),     # [10, 20]
        _pen(20, 5, 10, 20, Direction.DOWN),    # [5, 20]
        _pen(5, 8, 20, 30, Direction.UP),       # [5, 8] — no overlap with [10, 20]
    ]
    assert build_segments(pens) == []


# ═══════════════════════════════════════════════════════════
#  build_segments — snapshot properties
# ═══════════════════════════════════════════════════════════


def test_segment_snapshot_frozen() -> None:
    pens = _make_type1_up_segment_pens()
    segments = build_segments(pens)
    if segments:
        snap = segments[0]
        assert isinstance(snap, SegmentSnapshot)
        with pytest.raises(AttributeError):
            snap.high = 100.0  # type: ignore[misc]


def test_segment_snapshot_pens_tuple() -> None:
    pens = _make_type1_up_segment_pens()
    segments = build_segments(pens)
    if segments:
        assert isinstance(segments[0].pens, tuple)


# ═══════════════════════════════════════════════════════════
#  Fixed sample: 300811.SZ segments
# ═══════════════════════════════════════════════════════════


def _load_300811_pens() -> list[Pen]:
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
    return build_pens(confirmed)


def test_300811_has_segments() -> None:
    """300811.SZ should produce at least one confirmed segment."""
    pens = _load_300811_pens()
    segments = build_segments(pens)
    assert len(segments) >= 1
    for seg in segments:
        assert seg.state == SegmentState.CONFIRMED


def test_300811_segments_odd_pen_count() -> None:
    """Each confirmed segment should have an odd number of pens (≥3)."""
    pens = _load_300811_pens()
    segments = build_segments(pens)
    for seg in segments:
        pc = len(seg.pens)
        assert pc >= 3, f"Segment has {pc} pens"
        assert pc % 2 == 1, f"Segment has even pen count {pc}"


def test_300811_segments_direction_alternates() -> None:
    """Consecutive segments should alternate direction."""
    pens = _load_300811_pens()
    segments = build_segments(pens)
    for i in range(len(segments) - 1):
        assert segments[i].direction != segments[i + 1].direction, (
            f"Segments {i} and {i+1} have same direction"
        )
