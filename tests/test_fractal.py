"""Task 04 tests: fractal detection on merged K-line sequences."""

import csv
import os

import pytest

from chan_core.common.kline import MergedKLine
from chan_core.common.types import FractalType
from chan_core.structure._fractal import Fractal, find_fractals
from chan_core.structure._merge import merge_inclusive
from chan_core.common.kline import RawKLine


def _mk(high: float, low: float, idx: int = 0) -> MergedKLine:
    return MergedKLine(high=high, low=low, timestamp=f"t{idx}", source_indices=(idx,))


# ═══════════════════════════════════════════════════════════
#  Positive
# ═══════════════════════════════════════════════════════════


def test_top_fractal() -> None:
    bars = [_mk(5, 3, 0), _mk(8, 5, 1), _mk(6, 4, 2)]
    fs = find_fractals(bars)
    assert len(fs) == 1
    assert fs[0].type == FractalType.TOP
    assert fs[0].value == 8
    assert fs[0].index == 1


def test_bot_fractal() -> None:
    bars = [_mk(8, 5, 0), _mk(6, 3, 1), _mk(9, 4, 2)]
    fs = find_fractals(bars)
    assert len(fs) == 1
    assert fs[0].type == FractalType.BOT
    assert fs[0].value == 3
    assert fs[0].index == 1


def test_both_fractals_in_sequence() -> None:
    """5 bars: top at index 1, bot at index 3."""
    bars = [_mk(5, 3, 0), _mk(8, 5, 1), _mk(6, 4, 2), _mk(4, 1, 3), _mk(7, 3, 4)]
    fs = find_fractals(bars)
    assert len(fs) == 2
    assert fs[0].type == FractalType.TOP
    assert fs[0].index == 1
    assert fs[1].type == FractalType.BOT
    assert fs[1].index == 3


# ═══════════════════════════════════════════════════════════
#  Negative — strict inequality violations
# ═══════════════════════════════════════════════════════════


def test_top_fails_high_equal_left() -> None:
    """mid.high == left.high → NOT a top."""
    bars = [_mk(8, 3, 0), _mk(8, 5, 1), _mk(6, 4, 2)]
    assert find_fractals(bars) == []


def test_top_fails_high_equal_right() -> None:
    """mid.high == right.high → NOT a top."""
    bars = [_mk(5, 3, 0), _mk(8, 5, 1), _mk(8, 4, 2)]
    assert find_fractals(bars) == []


def test_top_fails_low_equal_left() -> None:
    """mid.low == left.low → NOT a top (four strict inequalities)."""
    bars = [_mk(5, 5, 0), _mk(8, 5, 1), _mk(6, 4, 2)]
    assert find_fractals(bars) == []


def test_top_fails_low_equal_right() -> None:
    """mid.low == right.low → NOT a top."""
    bars = [_mk(5, 3, 0), _mk(8, 5, 1), _mk(6, 5, 2)]
    assert find_fractals(bars) == []


def test_bot_fails_low_equal_left() -> None:
    """mid.low == left.low → NOT a bot."""
    bars = [_mk(8, 3, 0), _mk(6, 3, 1), _mk(9, 4, 2)]
    assert find_fractals(bars) == []


def test_bot_fails_low_equal_right() -> None:
    bars = [_mk(8, 5, 0), _mk(6, 3, 1), _mk(9, 3, 2)]
    assert find_fractals(bars) == []


def test_bot_fails_high_equal_left() -> None:
    """mid.high == left.high → NOT a bot (four strict inequalities)."""
    bars = [_mk(6, 5, 0), _mk(6, 3, 1), _mk(9, 4, 2)]
    assert find_fractals(bars) == []


def test_bot_fails_high_equal_right() -> None:
    bars = [_mk(8, 5, 0), _mk(6, 3, 1), _mk(6, 4, 2)]
    assert find_fractals(bars) == []


def test_high_satisfies_but_low_doesnt() -> None:
    """Top condition: high ok but low not strictly greater → no fractal."""
    bars = [_mk(5, 4, 0), _mk(8, 4, 1), _mk(6, 3, 2)]  # mid.low == left.low
    assert find_fractals(bars) == []


# ═══════════════════════════════════════════════════════════
#  Boundary
# ═══════════════════════════════════════════════════════════


def test_empty_sequence() -> None:
    assert find_fractals([]) == []


def test_one_bar() -> None:
    assert find_fractals([_mk(5, 3, 0)]) == []


def test_two_bars() -> None:
    assert find_fractals([_mk(5, 3, 0), _mk(8, 5, 1)]) == []


def test_three_bars_one_fractal() -> None:
    bars = [_mk(5, 3, 0), _mk(8, 5, 1), _mk(6, 4, 2)]
    assert len(find_fractals(bars)) == 1


def test_three_bars_no_fractal() -> None:
    """Monotonic increasing → no fractal."""
    bars = [_mk(3, 1, 0), _mk(5, 3, 1), _mk(7, 5, 2)]
    assert find_fractals(bars) == []


def test_adjacent_fractals_sharing_kline() -> None:
    """Two fractals sharing a K-line (left-right overlap).

    bars[1]=top, bars[3]=bot — they share no K-line.
    bars can also have adjacent fractals at [1] and [2] if
    the shared middle bar is both right-of-one and left-of-next.
    """
    # top at 1, bot at 3
    bars = [
        _mk(5, 3, 0),
        _mk(10, 6, 1),  # top
        _mk(7, 4, 2),
        _mk(4, 1, 3),   # bot
        _mk(6, 3, 4),
    ]
    fs = find_fractals(bars)
    assert len(fs) == 2
    assert fs[0].index == 1
    assert fs[1].index == 3


def test_first_last_cannot_be_middle() -> None:
    """First and last bars must not be fractal middle elements."""
    # Would be top at 0 if we checked it — but we don't.
    bars = [_mk(10, 8, 0), _mk(5, 3, 1), _mk(8, 5, 2)]
    fs = find_fractals(bars)
    # Index 0 can't be middle, index 1 is a bot
    assert len(fs) == 1
    assert fs[0].type == FractalType.BOT
    assert fs[0].index == 1


# ═══════════════════════════════════════════════════════════
#  Extreme
# ═══════════════════════════════════════════════════════════


def test_monotonic_increasing_no_top() -> None:
    bars = [_mk(float(i + 2), float(i + 1), i) for i in range(20)]
    assert all(f.type == FractalType.BOT for f in find_fractals(bars)) is True
    # Actually monotonic increasing has no fractals at all
    assert find_fractals(bars) == []


def test_monotonic_decreasing_no_bot() -> None:
    bars = [_mk(float(20 - i), float(19 - i), i) for i in range(20)]
    assert find_fractals(bars) == []


def test_alternating_zigzag() -> None:
    """Every other bar is a fractal in a zigzag."""
    # Pattern: low, HIGH, low, HIGH, low, ...
    bars = []
    for i in range(21):
        if i % 2 == 0:
            bars.append(_mk(3.0, 1.0, i))
        else:
            bars.append(_mk(8.0, 5.0, i))
    fs = find_fractals(bars)
    # Tops at odd indices, bots at even indices (not 0 and 20)
    tops = [f for f in fs if f.type == FractalType.TOP]
    bots = [f for f in fs if f.type == FractalType.BOT]
    assert len(tops) == 10  # indices 1,3,5,...,19
    assert len(bots) == 9   # indices 2,4,6,...,18


def test_all_same_no_fractal() -> None:
    """All bars identical → no strict inequality → no fractals."""
    bars = [_mk(5.0, 5.0, i) for i in range(10)]
    assert find_fractals(bars) == []


def test_fractal_klines_trace() -> None:
    """Fractal preserves its three K-line references."""
    bars = [_mk(5, 3, 0), _mk(8, 5, 1), _mk(6, 4, 2)]
    f = find_fractals(bars)[0]
    assert f.klines == (bars[0], bars[1], bars[2])


# ═══════════════════════════════════════════════════════════
#  Fixed sample: 300811.SZ first 6 fractals
# ═══════════════════════════════════════════════════════════


def _load_300811_merged() -> list[MergedKLine]:
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
    return merge_inclusive(raw)


_EXPECTED_FIRST_6_FRACTALS = [
    {"type": FractalType.TOP, "value": 42.36, "ts": "20250414"},
    {"type": FractalType.BOT, "value": 39.91, "ts": "20250416"},
    {"type": FractalType.TOP, "value": 42.66, "ts": "20250422"},
    {"type": FractalType.BOT, "value": 39.92, "ts": "20250429"},
    {"type": FractalType.TOP, "value": 43.21, "ts": "20250508"},
    {"type": FractalType.BOT, "value": 42.00, "ts": "20250509"},
]


def test_300811_first_6_fractals() -> None:
    merged = _load_300811_merged()
    fractals = find_fractals(merged)
    assert len(fractals) >= 6

    for i, exp in enumerate(_EXPECTED_FIRST_6_FRACTALS):
        f = fractals[i]
        assert f.type == exp["type"], f"Fractal {i}: expected {exp['type']}, got {f.type}"
        assert f.value == pytest.approx(exp["value"], abs=0.005), (
            f"Fractal {i}: expected value {exp['value']}, got {f.value}"
        )
        # Timestamp of middle K-line
        assert f.klines[1].timestamp == exp["ts"], (
            f"Fractal {i}: expected ts {exp['ts']}, got {f.klines[1].timestamp}"
        )


def test_300811_fractal_count() -> None:
    """300811.SZ: 181 merged → 84 fractals (42 top + 42 bot)."""
    merged = _load_300811_merged()
    fractals = find_fractals(merged)
    assert len(fractals) == 84
    tops = [f for f in fractals if f.type == FractalType.TOP]
    bots = [f for f in fractals if f.type == FractalType.BOT]
    assert len(tops) == 42
    assert len(bots) == 42
