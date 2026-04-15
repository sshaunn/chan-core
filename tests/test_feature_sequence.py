"""Task 07 tests: feature sequence construction and fractal detection."""

import pytest

from chan_core.common.kline import MergedKLine
from chan_core.common.types import Direction, FractalType
from chan_core.structure._fractal import Fractal
from chan_core.structure._pen import Pen
from chan_core.structure._feature_sequence import (
    FeatureElement,
    build_feature_sequence,
    check_bot_fseq,
    check_top_fseq,
    merge_feature_sequence,
)


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


def _fe(high: float, low: float) -> FeatureElement:
    """Synthetic feature element (no real source pen)."""
    p = _pen(low, high, 1, 10, Direction.UP)
    return FeatureElement(high=high, low=low, source_pens=(p,))


# ═══════════════════════════════════════════════════════════
#  build_feature_sequence
# ═══════════════════════════════════════════════════════════


def test_build_fseq_up_segment() -> None:
    """UP segment → feature sequence is DOWN pens."""
    pens = [
        _pen(10, 20, 1, 10, Direction.UP),
        _pen(20, 15, 10, 20, Direction.DOWN),
        _pen(15, 25, 20, 30, Direction.UP),
        _pen(25, 18, 30, 40, Direction.DOWN),
        _pen(18, 28, 40, 50, Direction.UP),
    ]
    fs = build_feature_sequence(pens, Direction.UP)
    assert len(fs) == 2  # 2 DOWN pens
    assert fs[0].high == 20 and fs[0].low == 15
    assert fs[1].high == 25 and fs[1].low == 18


def test_build_fseq_down_segment() -> None:
    """DOWN segment → feature sequence is UP pens."""
    pens = [
        _pen(20, 10, 1, 10, Direction.DOWN),
        _pen(10, 18, 10, 20, Direction.UP),
        _pen(18, 8, 20, 30, Direction.DOWN),
    ]
    fs = build_feature_sequence(pens, Direction.DOWN)
    assert len(fs) == 1
    assert fs[0].high == 18 and fs[0].low == 10


def test_build_fseq_empty_pens() -> None:
    assert build_feature_sequence([], Direction.UP) == []


def test_build_fseq_no_opposite_pens() -> None:
    """All pens are same direction as segment → empty feature sequence."""
    pens = [_pen(10, 20, 1, 10, Direction.UP)]
    fs = build_feature_sequence(pens, Direction.UP)
    assert fs == []


# ═══════════════════════════════════════════════════════════
#  merge_feature_sequence
# ═══════════════════════════════════════════════════════════


def test_merge_fseq_no_inclusion() -> None:
    elements = [_fe(10, 5), _fe(15, 8), _fe(20, 12)]
    merged = merge_feature_sequence(elements)
    assert len(merged) == 3


def test_merge_fseq_with_inclusion() -> None:
    """Second element contained in first → merge."""
    elements = [_fe(10, 2), _fe(8, 4), _fe(15, 6)]
    merged = merge_feature_sequence(elements)
    assert len(merged) == 2
    assert merged[0].source_pens == elements[0].source_pens + elements[1].source_pens


def test_merge_fseq_empty() -> None:
    assert merge_feature_sequence([]) == []


def test_merge_fseq_single() -> None:
    elements = [_fe(10, 5)]
    merged = merge_feature_sequence(elements)
    assert len(merged) == 1


def test_merge_fseq_all_inclusive() -> None:
    """All elements contained in the running merge → merge into 1."""
    # [20,1] + [15,5] → UP merge → [20,5]; then [18,6] contained in [20,5]
    elements = [_fe(20, 1), _fe(15, 5), _fe(18, 6)]
    merged = merge_feature_sequence(elements)
    assert len(merged) == 1
    total_pens = sum(len(m.source_pens) for m in merged)
    assert total_pens == 3


# ═══════════════════════════════════════════════════════════
#  check_top_fseq / check_bot_fseq
# ═══════════════════════════════════════════════════════════


# ── Positive ──────────────────────────────────────────────


def test_top_fseq_positive() -> None:
    seq = [_fe(5, 3), _fe(8, 5), _fe(6, 4)]
    assert check_top_fseq(seq, 1) is True


def test_bot_fseq_positive() -> None:
    seq = [_fe(8, 5), _fe(6, 3), _fe(9, 4)]
    assert check_bot_fseq(seq, 1) is True


# ── Negative (strict inequality) ─────────────────────────


def test_top_fseq_equal_high_left() -> None:
    seq = [_fe(8, 3), _fe(8, 5), _fe(6, 4)]
    assert check_top_fseq(seq, 1) is False


def test_top_fseq_equal_low_right() -> None:
    seq = [_fe(5, 3), _fe(8, 5), _fe(6, 5)]
    assert check_top_fseq(seq, 1) is False


def test_bot_fseq_equal_low_left() -> None:
    seq = [_fe(8, 3), _fe(6, 3), _fe(9, 4)]
    assert check_bot_fseq(seq, 1) is False


def test_bot_fseq_equal_high_right() -> None:
    seq = [_fe(8, 5), _fe(6, 3), _fe(6, 4)]
    assert check_bot_fseq(seq, 1) is False


# ── Boundary ──────────────────────────────────────────────


def test_fseq_less_than_3_elements() -> None:
    seq = [_fe(5, 3), _fe(8, 5)]
    assert check_top_fseq(seq, 1) is False
    assert check_bot_fseq(seq, 1) is False


def test_fseq_index_out_of_range() -> None:
    seq = [_fe(5, 3), _fe(8, 5), _fe(6, 4)]
    assert check_top_fseq(seq, 0) is False  # first element
    assert check_top_fseq(seq, 2) is False  # last element
    assert check_top_fseq(seq, -1) is False


# ── Extreme ───────────────────────────────────────────────


def test_fseq_multiple_fractals() -> None:
    """Sequence with both top and bottom fractals."""
    seq = [_fe(5, 3), _fe(8, 5), _fe(6, 4), _fe(3, 1), _fe(5, 2)]
    assert check_top_fseq(seq, 1) is True
    assert check_bot_fseq(seq, 3) is True


def test_fseq_all_same_no_fractal() -> None:
    seq = [_fe(5, 3)] * 5
    for j in range(1, 4):
        assert check_top_fseq(seq, j) is False
        assert check_bot_fseq(seq, j) is False


def test_feature_element_frozen() -> None:
    fe = _fe(10, 5)
    with pytest.raises(AttributeError):
        fe.high = 20.0  # type: ignore[misc]


def test_feature_element_interval() -> None:
    fe = _fe(10, 5)
    assert fe.interval == (5, 10)
