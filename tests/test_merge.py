"""Task 03 tests: inclusion-relationship merge engine."""

import csv
import os

import pytest

from chan_core.common.kline import MergedKLine, RawKLine
from chan_core.common.types import Direction
from chan_core.structure._merge import (
    get_merge_direction,
    has_inclusion,
    merge_inclusive,
    merge_two,
)


# ═══════════════════════════════════════════════════════════
#  has_inclusion
# ═══════════════════════════════════════════════════════════


def _mk(high: float, low: float, idx: int = 0) -> MergedKLine:
    return MergedKLine(high=high, low=low, timestamp="t", source_indices=(idx,))


# ── Positive ──────────────────────────────────────────────


def test_inclusion_a_contains_b() -> None:
    assert has_inclusion(_mk(10, 1), _mk(8, 2)) is True


def test_inclusion_b_contains_a() -> None:
    assert has_inclusion(_mk(8, 2), _mk(10, 1)) is True


def test_inclusion_identical() -> None:
    """Identical bars: mutual inclusion."""
    assert has_inclusion(_mk(5, 5), _mk(5, 5)) is True


def test_inclusion_equal_bars() -> None:
    assert has_inclusion(_mk(10, 5), _mk(10, 5)) is True


# ── Negative ──────────────────────────────────────────────


def test_no_inclusion_disjoint() -> None:
    assert has_inclusion(_mk(5, 3), _mk(8, 6)) is False


def test_no_inclusion_partial_overlap() -> None:
    """Partial overlap but neither contains the other."""
    assert has_inclusion(_mk(10, 5), _mk(12, 8)) is False


# ── Boundary ──────────────────────────────────────────────


def test_inclusion_one_side_equal_high() -> None:
    """a.high == b.high, a.low < b.low → a contains b."""
    assert has_inclusion(_mk(10, 3), _mk(10, 5)) is True


def test_inclusion_one_side_equal_low() -> None:
    """a.low == b.low, a.high > b.high → a contains b."""
    assert has_inclusion(_mk(10, 5), _mk(8, 5)) is True


# ═══════════════════════════════════════════════════════════
#  get_merge_direction
# ═══════════════════════════════════════════════════════════


def test_direction_no_prev_defaults_up() -> None:
    assert get_merge_direction(_mk(10, 5), None) == Direction.UP


def test_direction_up() -> None:
    prev = _mk(8, 4)
    cur = _mk(10, 5)
    assert get_merge_direction(cur, prev) == Direction.UP


def test_direction_down() -> None:
    prev = _mk(10, 5)
    cur = _mk(8, 3)
    assert get_merge_direction(cur, prev) == Direction.DOWN


# ═══════════════════════════════════════════════════════════
#  merge_two
# ═══════════════════════════════════════════════════════════


def test_merge_two_up() -> None:
    a = MergedKLine(high=10, low=5, timestamp="t1", source_indices=(0,))
    b = MergedKLine(high=9, low=6, timestamp="t2", source_indices=(1,))
    m = merge_two(a, b, Direction.UP)
    assert m.high == 10
    assert m.low == 6
    assert m.source_indices == (0, 1)
    assert m.timestamp == "t2"  # last bar's timestamp


def test_merge_two_down() -> None:
    a = MergedKLine(high=10, low=5, timestamp="t1", source_indices=(0,))
    b = MergedKLine(high=9, low=6, timestamp="t2", source_indices=(1,))
    m = merge_two(a, b, Direction.DOWN)
    assert m.high == 9
    assert m.low == 5
    assert m.source_indices == (0, 1)


# ═══════════════════════════════════════════════════════════
#  merge_inclusive — full pipeline
# ═══════════════════════════════════════════════════════════


# ── Positive ──────────────────────────────────────────────


def test_merge_with_inclusion_pair() -> None:
    """Second bar is contained by first → merge."""
    raw = [
        RawKLine(high=10, low=1, timestamp="t0"),
        RawKLine(high=8, low=3, timestamp="t1"),
        RawKLine(high=12, low=5, timestamp="t2"),
    ]
    result = merge_inclusive(raw)
    assert len(result) == 2
    assert result[0].source_indices == (0, 1)
    assert result[1].source_indices == (2,)


# ── Negative ──────────────────────────────────────────────


def test_merge_no_inclusion() -> None:
    """No inclusion → output length == input length."""
    raw = [
        RawKLine(high=3, low=1, timestamp="t0"),
        RawKLine(high=5, low=4, timestamp="t1"),
        RawKLine(high=7, low=6, timestamp="t2"),
    ]
    result = merge_inclusive(raw)
    assert len(result) == 3
    for i, m in enumerate(result):
        assert m.source_indices == (i,)


# ── Boundary ──────────────────────────────────────────────


def test_merge_empty() -> None:
    assert merge_inclusive([]) == []


def test_merge_single() -> None:
    raw = [RawKLine(high=10, low=5, timestamp="t0")]
    result = merge_inclusive(raw)
    assert len(result) == 1
    assert result[0].high == 10
    assert result[0].low == 5


def test_merge_two_bars_inclusion() -> None:
    raw = [
        RawKLine(high=10, low=1, timestamp="t0"),
        RawKLine(high=8, low=3, timestamp="t1"),
    ]
    result = merge_inclusive(raw)
    assert len(result) == 1
    assert result[0].source_indices == (0, 1)


def test_merge_three_consecutive_inclusion() -> None:
    """Three bars where each is contained in the running merge → merge into 1."""
    raw = [
        RawKLine(high=10, low=1, timestamp="t0"),
        RawKLine(high=8, low=3, timestamp="t1"),
        RawKLine(high=7, low=4, timestamp="t2"),  # contained in merged(0,1)=(10,3)
    ]
    result = merge_inclusive(raw)
    assert len(result) == 1
    assert result[0].source_indices == (0, 1, 2)


def test_merge_first_no_prev_defaults_up() -> None:
    """At sequence start, merge direction defaults to UP."""
    raw = [
        RawKLine(high=10, low=5, timestamp="t0"),
        RawKLine(high=9, low=6, timestamp="t1"),  # contained, UP → max(h), max(l)
    ]
    result = merge_inclusive(raw)
    assert len(result) == 1
    assert result[0].high == 10  # max(10, 9)
    assert result[0].low == 6  # max(5, 6)


# ── Extreme ───────────────────────────────────────────────


def test_merge_100_consecutive_inclusion() -> None:
    """100 bars all contained in the first → merge into 1."""
    raw = [RawKLine(high=100, low=1, timestamp=f"t{i}") for i in range(100)]
    # All have same range so all are mutually inclusive
    result = merge_inclusive(raw)
    assert len(result) == 1
    assert len(result[0].source_indices) == 100
    assert result[0].source_indices == tuple(range(100))


def test_merge_all_non_inclusive() -> None:
    """Monotonic increasing → no inclusion, length preserved."""
    raw = [
        RawKLine(high=float(2 * i + 2), low=float(2 * i + 1), timestamp=f"t{i}")
        for i in range(50)
    ]
    result = merge_inclusive(raw)
    assert len(result) == 50


def test_merge_identical_bars() -> None:
    """All bars identical (h=l=5) → all merged into 1."""
    raw = [RawKLine(high=5, low=5, timestamp=f"t{i}") for i in range(10)]
    result = merge_inclusive(raw)
    assert len(result) == 1
    assert len(result[0].source_indices) == 10


def test_source_indices_no_duplicate_no_gap() -> None:
    """Every raw index appears exactly once across all merged bars."""
    raw = [
        RawKLine(high=10, low=1, timestamp="t0"),
        RawKLine(high=8, low=3, timestamp="t1"),
        RawKLine(high=12, low=5, timestamp="t2"),
        RawKLine(high=11, low=6, timestamp="t3"),
        RawKLine(high=15, low=8, timestamp="t4"),
    ]
    result = merge_inclusive(raw)
    all_indices = []
    for m in result:
        all_indices.extend(m.source_indices)
    assert sorted(all_indices) == list(range(len(raw)))


def test_merged_no_adjacent_inclusion() -> None:
    """Post-condition: no two adjacent merged bars have inclusion."""
    raw = [
        RawKLine(high=10, low=1, timestamp="t0"),
        RawKLine(high=8, low=3, timestamp="t1"),
        RawKLine(high=12, low=5, timestamp="t2"),
        RawKLine(high=11, low=6, timestamp="t3"),
        RawKLine(high=15, low=8, timestamp="t4"),
        RawKLine(high=14, low=9, timestamp="t5"),
        RawKLine(high=7, low=2, timestamp="t6"),
    ]
    result = merge_inclusive(raw)
    for i in range(len(result) - 1):
        assert not has_inclusion(result[i], result[i + 1]), (
            f"Adjacent inclusion at {i}: {result[i]} vs {result[i+1]}"
        )


# ═══════════════════════════════════════════════════════════
#  Fixed sample alignment: 300811.SZ first 10 merged K-lines
# ═══════════════════════════════════════════════════════════


def _load_300811_raw() -> list[RawKLine]:
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
    return raw


# Expected first 10 merged K-lines from 最终稿 §13.1
_EXPECTED_FIRST_10 = [
    {"high": 41.40, "low": 40.18, "ts": "20250411", "count": 1, "indices": [0]},
    {"high": 42.36, "low": 41.31, "ts": "20250414", "count": 1, "indices": [1]},
    {"high": 41.52, "low": 40.79, "ts": "20250415", "count": 1, "indices": [2]},
    {"high": 41.04, "low": 39.91, "ts": "20250416", "count": 1, "indices": [3]},
    {"high": 42.00, "low": 40.73, "ts": "20250418", "count": 2, "indices": [4, 5]},
    {"high": 42.16, "low": 40.77, "ts": "20250421", "count": 1, "indices": [6]},
    {"high": 42.66, "low": 41.74, "ts": "20250422", "count": 1, "indices": [7]},
    {"high": 40.88, "low": 39.99, "ts": "20250428", "count": 4, "indices": [8, 9, 10, 11]},
    {"high": 40.55, "low": 39.92, "ts": "20250429", "count": 1, "indices": [12]},
    {"high": 40.60, "low": 40.05, "ts": "20250430", "count": 1, "indices": [13]},
]


def test_300811_first_10_merged() -> None:
    """Align with 最终稿 §13.1 table: first 10 merged K-lines."""
    raw = _load_300811_raw()
    merged = merge_inclusive(raw)

    assert len(merged) >= 10, f"Expected ≥ 10 merged bars, got {len(merged)}"

    for i, exp in enumerate(_EXPECTED_FIRST_10):
        m = merged[i]
        assert m.high == pytest.approx(exp["high"], abs=0.005), (
            f"Bar {i} high: expected {exp['high']}, got {m.high}"
        )
        assert m.low == pytest.approx(exp["low"], abs=0.005), (
            f"Bar {i} low: expected {exp['low']}, got {m.low}"
        )
        assert m.timestamp == exp["ts"], (
            f"Bar {i} timestamp: expected {exp['ts']}, got {m.timestamp}"
        )
        assert len(m.source_indices) == exp["count"], (
            f"Bar {i} merge count: expected {exp['count']}, got {len(m.source_indices)}"
        )
        assert list(m.source_indices) == exp["indices"], (
            f"Bar {i} indices: expected {exp['indices']}, got {list(m.source_indices)}"
        )


def test_300811_total_merged_count() -> None:
    """300811.SZ: 242 raw → 181 merged (merged 61)."""
    raw = _load_300811_raw()
    merged = merge_inclusive(raw)
    assert len(raw) == 242, f"Expected 242 raw bars, got {len(raw)}"
    assert len(merged) == 181, f"Expected 181 merged bars, got {len(merged)}"


def test_300811_zero_inclusion_post_merge() -> None:
    """Post-merge: no adjacent inclusion in 300811 merged sequence."""
    raw = _load_300811_raw()
    merged = merge_inclusive(raw)
    for i in range(len(merged) - 1):
        assert not has_inclusion(merged[i], merged[i + 1]), (
            f"Inclusion at index {i}: {merged[i]} vs {merged[i+1]}"
        )


def test_300811_source_indices_complete() -> None:
    """Every raw index appears exactly once."""
    raw = _load_300811_raw()
    merged = merge_inclusive(raw)
    all_indices: list[int] = []
    for m in merged:
        all_indices.extend(m.source_indices)
    assert sorted(all_indices) == list(range(len(raw)))
