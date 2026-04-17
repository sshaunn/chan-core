"""Task 05 tests: pen confirmed-list algorithm."""

import csv
import os

import pytest

from chan_core.common.kline import MergedKLine, RawKLine
from chan_core.common.types import Direction, FractalType
from chan_core.structure._fractal import Fractal, find_fractals
from chan_core.structure._merge import merge_inclusive
from chan_core.structure._pen import (
    Pen,
    build_confirmed,
    build_pens,
    check_c1,
    check_c2,
    check_c4,
)


# ── Helpers ───────────────────────────────────────────────


def _mk(high: float, low: float, idx: int) -> MergedKLine:
    return MergedKLine(high=high, low=low, timestamp=f"t{idx}", source_indices=(idx,))


def _top(value: float, idx: int) -> Fractal:
    """Construct a synthetic TOP fractal at merged index `idx`."""
    left = _mk(value - 2, value - 4, idx - 1)
    mid = _mk(value, value - 2, idx)
    right = _mk(value - 2, value - 4, idx + 1)
    return Fractal(type=FractalType.TOP, value=value, klines=(left, mid, right), index=idx)


def _bot(value: float, idx: int) -> Fractal:
    """Construct a synthetic BOT fractal at merged index `idx`."""
    left = _mk(value + 4, value + 2, idx - 1)
    mid = _mk(value + 2, value, idx)
    right = _mk(value + 4, value + 2, idx + 1)
    return Fractal(type=FractalType.BOT, value=value, klines=(left, mid, right), index=idx)


# ═══════════════════════════════════════════════════════════
#  check_c1 — fractal independence
# ═══════════════════════════════════════════════════════════


def test_c1_disjoint() -> None:
    assert check_c1(_top(10, 3), _bot(5, 6)) is True  # gap=3


def test_c1_shared_kline() -> None:
    assert check_c1(_top(10, 1), _bot(5, 3)) is False  # gap=2, share index 2


def test_c1_adjacent_no_share() -> None:
    assert check_c1(_top(10, 1), _bot(5, 4)) is True  # gap=3


def test_c1_same_index() -> None:
    assert check_c1(_top(10, 5), _bot(5, 5)) is False


# ═══════════════════════════════════════════════════════════
#  check_c2 — raw K-line gap between fractal extremes
# ═══════════════════════════════════════════════════════════


def test_c2_raw_gap_4_passes() -> None:
    """Raw index gap = 5 → ≥ 3 → passes."""
    a = _top(10, 1)
    b = _bot(5, 6)  # raw gap = 6 - 1 = 5
    assert check_c2(a, b) is True


def test_c2_raw_gap_3_fails() -> None:
    """Raw index gap = 3 → below ≥ 4 threshold → fails."""
    a = _top(10, 1)
    b = _bot(5, 4)  # raw gap = 4 - 1 = 3
    assert check_c2(a, b) is False


def test_c2_raw_gap_2_fails() -> None:
    """Raw index gap = 2 → below threshold → fails."""
    a = _top(10, 1)
    b = _bot(5, 3)  # raw gap = 3 - 1 = 2
    assert check_c2(a, b) is False


def test_c2_raw_gap_1_fails() -> None:
    """Raw index gap = 1 → fails."""
    a = _top(10, 1)
    b = _bot(5, 2)  # raw gap = 2 - 1 = 1
    assert check_c2(a, b) is False


def test_c2_raw_gap_large_passes() -> None:
    """Large gap always passes."""
    a = _top(10, 1)
    b = _bot(5, 20)  # raw gap = 19
    assert check_c2(a, b) is True


# ═══════════════════════════════════════════════════════════
#  check_c4 — price validity
# ═══════════════════════════════════════════════════════════


def test_c4_top_gt_bot() -> None:
    assert check_c4(_top(10, 3), _bot(5, 8)) is True


def test_c4_top_eq_bot() -> None:
    """Equal values → fails (strict)."""
    assert check_c4(_top(10, 3), _bot(10, 8)) is False


def test_c4_top_lt_bot() -> None:
    assert check_c4(_top(5, 3), _bot(10, 8)) is False


def test_c4_reversed_order() -> None:
    """Bot first, then top — still checks val(top) > val(bot)."""
    assert check_c4(_bot(5, 3), _top(10, 8)) is True


# ═══════════════════════════════════════════════════════════
#  build_confirmed
# ═══════════════════════════════════════════════════════════


def test_confirmed_empty() -> None:
    assert build_confirmed([]) == []


def test_confirmed_single() -> None:
    f = _top(10, 5)
    assert build_confirmed([f]) == [f]


def test_confirmed_same_type_keeps_extreme() -> None:
    """Two consecutive tops → keep the higher one."""
    f1 = _top(10, 5)
    f2 = _top(12, 10)
    result = build_confirmed([f1, f2])
    assert len(result) == 1
    assert result[0].value == 12


def test_confirmed_same_type_bot_keeps_lower() -> None:
    f1 = _bot(5, 5)
    f2 = _bot(3, 10)
    result = build_confirmed([f1, f2])
    assert len(result) == 1
    assert result[0].value == 3


def test_confirmed_two_same_type_keeps_first_if_more_extreme() -> None:
    f1 = _top(15, 5)
    f2 = _top(12, 10)
    result = build_confirmed([f1, f2])
    assert len(result) == 1
    assert result[0].value == 15


def test_confirmed_opposite_all_pass() -> None:
    """Opposite type, all conditions met → appended."""
    t = _top(10, 5)
    b = _bot(3, 15)  # gap=10 → C1 ok, bars_between=9 → C2 ok, 10>3 → C4 ok
    result = build_confirmed([t, b])
    assert len(result) == 2


def test_confirmed_opposite_c1_fail_skips() -> None:
    """Opposite type, C1 fails → skipped."""
    t = _top(10, 5)
    b = _bot(3, 7)  # gap=2 → C1 fails
    result = build_confirmed([t, b])
    assert len(result) == 1


def test_confirmed_opposite_c2_fail_skips() -> None:
    """Opposite type, C1 passes but C2 fails (raw gap < 3) → skipped.

    With raw K-line gap C2, we need merged index gap ≥ 3 (C1 pass) but
    raw gap < 3 (C2 fail). This requires multi-element source_indices
    so the merged bar's last raw index is close to the next bar's first.
    """
    # Build fractals with multi-element source_indices to decouple merged/raw gap
    # TOP at merged index 5, middle kline covers raw indices 5,6,7
    left_t = MergedKLine(high=8, low=6, timestamp="t4", source_indices=(4,))
    mid_t = MergedKLine(high=10, low=8, timestamp="t5", source_indices=(5, 6, 7))
    right_t = MergedKLine(high=8, low=6, timestamp="t6", source_indices=(8,))
    t = Fractal(type=FractalType.TOP, value=10, klines=(left_t, mid_t, right_t), index=5)

    # BOT at merged index 8, middle kline covers raw indices 9
    # merged gap = 3 → C1 passes (no shared klines: 4,5,6 vs 7,8,9)
    # raw gap = min(9) - max(5,6,7) = 9 - 7 = 2 → C2 fails
    left_b = MergedKLine(high=7, low=5, timestamp="t7", source_indices=(9,))
    mid_b = MergedKLine(high=5, low=3, timestamp="t8", source_indices=(9,))
    right_b = MergedKLine(high=7, low=5, timestamp="t9", source_indices=(10,))
    b = Fractal(type=FractalType.BOT, value=3, klines=(left_b, mid_b, right_b), index=8)

    result = build_confirmed([t, b])
    assert len(result) == 1


def test_confirmed_alternates() -> None:
    """Confirmed list always alternates types."""
    t1 = _top(10, 5)
    b1 = _bot(3, 15)
    t2 = _top(12, 25)
    b2 = _bot(1, 35)
    result = build_confirmed([t1, b1, t2, b2])
    for i in range(len(result) - 1):
        assert result[i].type != result[i + 1].type


# ═══════════════════════════════════════════════════════════
#  build_pens
# ═══════════════════════════════════════════════════════════


def test_build_pens_empty() -> None:
    assert build_pens([]) == []


def test_build_pens_single_fractal() -> None:
    assert build_pens([_top(10, 5)]) == []


def test_build_pens_one_pen() -> None:
    confirmed = [_top(10, 5), _bot(3, 15)]
    pens = build_pens(confirmed)
    assert len(pens) == 1
    assert pens[0].direction == Direction.DOWN
    assert pens[0].high == 10
    assert pens[0].low == 3


def test_build_pens_direction_alternates() -> None:
    confirmed = [_top(10, 5), _bot(3, 15), _top(12, 25), _bot(1, 35)]
    pens = build_pens(confirmed)
    assert len(pens) == 3
    assert pens[0].direction == Direction.DOWN
    assert pens[1].direction == Direction.UP
    assert pens[2].direction == Direction.DOWN


def test_build_pens_zero_gap() -> None:
    """pen[k].end == pen[k+1].start (zero-gap property)."""
    confirmed = [_top(10, 5), _bot(3, 15), _top(12, 25)]
    pens = build_pens(confirmed)
    assert pens[0].end is pens[1].start


def test_pen_high_low() -> None:
    """Pen high/low computed from fractal values."""
    confirmed = [_bot(3, 5), _top(10, 15)]
    pens = build_pens(confirmed)
    assert pens[0].direction == Direction.UP
    assert pens[0].high == 10
    assert pens[0].low == 3
    assert pens[0].interval == (3, 10)


# ═══════════════════════════════════════════════════════════
#  Pen immutability
# ═══════════════════════════════════════════════════════════


def test_pen_frozen() -> None:
    confirmed = [_top(10, 5), _bot(3, 15)]
    pen = build_pens(confirmed)[0]
    with pytest.raises(AttributeError):
        pen.direction = Direction.UP  # type: ignore[misc]


# ═══════════════════════════════════════════════════════════
#  Extreme
# ═══════════════════════════════════════════════════════════


def test_many_same_type_only_keeps_extreme() -> None:
    """20 consecutive tops → confirmed keeps only the highest."""
    fractals = [_top(float(i), i * 5) for i in range(1, 21)]
    result = build_confirmed(fractals)
    assert len(result) == 1
    assert result[0].value == 20.0


def test_all_opposite_fail_c2() -> None:
    """Alternating types but all fail C2 → confirmed has 1 element."""
    fractals: list[Fractal] = []
    for i in range(10):
        idx = i * 2 + 1  # indices 1, 3, 5, ... → gap=2, C1 fails
        if i % 2 == 0:
            fractals.append(_top(float(10 + i), idx))
        else:
            fractals.append(_bot(float(5 - i), idx))
    result = build_confirmed(fractals)
    assert len(result) == 1


# ═══════════════════════════════════════════════════════════
#  Fixed sample: 300811.SZ 21 pens
# ═══════════════════════════════════════════════════════════


def _load_300811_pens() -> list[Pen]:
    """Load 300811.SZ raw K-lines from CSV."""
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


_EXPECTED_PENS = [
    {"dir": Direction.DOWN, "start_val": 44.07, "end_val": 39.98, "high": 44.07, "low": 39.98},
    {"dir": Direction.UP, "start_val": 39.98, "end_val": 44.88, "high": 44.88, "low": 39.98},
    {"dir": Direction.DOWN, "start_val": 44.88, "end_val": 40.51, "high": 44.88, "low": 40.51},
    {"dir": Direction.UP, "start_val": 40.51, "end_val": 62.53, "high": 62.53, "low": 40.51},
    {"dir": Direction.DOWN, "start_val": 62.53, "end_val": 54.40, "high": 62.53, "low": 54.40},
    {"dir": Direction.UP, "start_val": 54.40, "end_val": 77.95, "high": 77.95, "low": 54.40},
    {"dir": Direction.DOWN, "start_val": 77.95, "end_val": 69.70, "high": 77.95, "low": 69.70},
    {"dir": Direction.UP, "start_val": 69.70, "end_val": 82.50, "high": 82.50, "low": 69.70},
    {"dir": Direction.DOWN, "start_val": 82.50, "end_val": 68.01, "high": 82.50, "low": 68.01},
    {"dir": Direction.UP, "start_val": 68.01, "end_val": 79.77, "high": 79.77, "low": 68.01},
    {"dir": Direction.DOWN, "start_val": 79.77, "end_val": 68.59, "high": 79.77, "low": 68.59},
    {"dir": Direction.UP, "start_val": 68.59, "end_val": 87.36, "high": 87.36, "low": 68.59},
    {"dir": Direction.DOWN, "start_val": 87.36, "end_val": 65.10, "high": 87.36, "low": 65.10},
    {"dir": Direction.UP, "start_val": 65.10, "end_val": 76.78, "high": 76.78, "low": 65.10},
    {"dir": Direction.DOWN, "start_val": 76.78, "end_val": 67.53, "high": 76.78, "low": 67.53},
    {"dir": Direction.UP, "start_val": 67.53, "end_val": 84.10, "high": 84.10, "low": 67.53},
    {"dir": Direction.DOWN, "start_val": 84.10, "end_val": 73.05, "high": 84.10, "low": 73.05},
    {"dir": Direction.UP, "start_val": 73.05, "end_val": 91.00, "high": 91.00, "low": 73.05},
    {"dir": Direction.DOWN, "start_val": 91.00, "end_val": 75.03, "high": 91.00, "low": 75.03},
    {"dir": Direction.UP, "start_val": 75.03, "end_val": 81.96, "high": 81.96, "low": 75.03},
    {"dir": Direction.DOWN, "start_val": 81.96, "end_val": 72.75, "high": 81.96, "low": 72.75},
]


def test_300811_pen_count() -> None:
    pens = _load_300811_pens()
    assert len(pens) == 21, f"Expected 21 pens, got {len(pens)}"


def test_300811_pen_values() -> None:
    pens = _load_300811_pens()
    for i, exp in enumerate(_EXPECTED_PENS):
        p = pens[i]
        assert p.direction == exp["dir"], (
            f"Pen {i}: expected {exp['dir']}, got {p.direction}"
        )
        assert p.start.value == pytest.approx(exp["start_val"], abs=0.005), (
            f"Pen {i}: start expected {exp['start_val']}, got {p.start.value}"
        )
        assert p.end.value == pytest.approx(exp["end_val"], abs=0.005), (
            f"Pen {i}: end expected {exp['end_val']}, got {p.end.value}"
        )
        assert p.high == pytest.approx(exp["high"], abs=0.005), (
            f"Pen {i}: high expected {exp['high']}, got {p.high}"
        )
        assert p.low == pytest.approx(exp["low"], abs=0.005), (
            f"Pen {i}: low expected {exp['low']}, got {p.low}"
        )


def test_300811_zero_gap() -> None:
    """pen[k].end == pen[k+1].start for all adjacent pens."""
    pens = _load_300811_pens()
    for i in range(len(pens) - 1):
        assert pens[i].end is pens[i + 1].start, (
            f"Gap at pen {i}/{i+1}: end={pens[i].end} != start={pens[i+1].start}"
        )


def test_300811_direction_alternates() -> None:
    """All adjacent pens have opposite directions."""
    pens = _load_300811_pens()
    for i in range(len(pens) - 1):
        assert pens[i].direction != pens[i + 1].direction, (
            f"Direction not alternating at pen {i}/{i+1}"
        )
