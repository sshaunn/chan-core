"""Task 02 tests: RawKLine and MergedKLine frozen dataclasses."""

import pytest

from chan_core.common.kline import MergedKLine, RawKLine


# ═══════════════════════════════════════════════════════════
#  RawKLine
# ═══════════════════════════════════════════════════════════


# ── Positive ──────────────────────────────────────────────


def test_raw_kline_valid() -> None:
    k = RawKLine(high=10.0, low=5.0, timestamp="20250101")
    assert k.high == 10.0
    assert k.low == 5.0
    assert k.timestamp == "20250101"


def test_raw_kline_interval() -> None:
    k = RawKLine(high=10.0, low=5.0, timestamp="20250101")
    assert k.interval == (5.0, 10.0)


# ── Negative ──────────────────────────────────────────────


def test_raw_kline_low_gt_high() -> None:
    with pytest.raises(ValueError, match="low.*must be <= high"):
        RawKLine(high=5.0, low=10.0, timestamp="20250101")


# ── Boundary ──────────────────────────────────────────────


def test_raw_kline_equal_high_low() -> None:
    k = RawKLine(high=5.0, low=5.0, timestamp="20250101")
    assert k.high == k.low == 5.0
    assert k.interval == (5.0, 5.0)


# ── Extreme ───────────────────────────────────────────────


def test_raw_kline_large_values() -> None:
    k = RawKLine(high=1e15, low=1e-15, timestamp="20250101")
    assert k.high == 1e15
    assert k.low == 1e-15


def test_raw_kline_zero_values() -> None:
    k = RawKLine(high=0.0, low=0.0, timestamp="20250101")
    assert k.interval == (0.0, 0.0)


# ── Immutability ──────────────────────────────────────────


def test_raw_kline_frozen() -> None:
    k = RawKLine(high=10.0, low=5.0, timestamp="20250101")
    with pytest.raises(AttributeError):
        k.high = 20.0  # type: ignore[misc]
    with pytest.raises(AttributeError):
        k.low = 1.0  # type: ignore[misc]
    with pytest.raises(AttributeError):
        k.timestamp = "20250102"  # type: ignore[misc]


# ═══════════════════════════════════════════════════════════
#  MergedKLine
# ═══════════════════════════════════════════════════════════


# ── Positive ──────────────────────────────────────────────


def test_merged_kline_valid() -> None:
    m = MergedKLine(high=10.0, low=5.0, timestamp="20250101", source_indices=(0, 1))
    assert m.high == 10.0
    assert m.low == 5.0
    assert m.source_indices == (0, 1)


def test_merged_kline_interval() -> None:
    m = MergedKLine(high=10.0, low=5.0, timestamp="20250101", source_indices=(0,))
    assert m.interval == (5.0, 10.0)


def test_merged_kline_single_source() -> None:
    m = MergedKLine(high=10.0, low=5.0, timestamp="20250101", source_indices=(42,))
    assert m.source_indices == (42,)


# ── Negative ──────────────────────────────────────────────


def test_merged_kline_low_gt_high() -> None:
    with pytest.raises(ValueError, match="low.*must be <= high"):
        MergedKLine(high=5.0, low=10.0, timestamp="20250101", source_indices=(0,))


# ── Boundary ──────────────────────────────────────────────


def test_merged_kline_equal_high_low() -> None:
    m = MergedKLine(high=5.0, low=5.0, timestamp="20250101", source_indices=(0,))
    assert m.high == m.low == 5.0


def test_merged_kline_empty_source_indices() -> None:
    """Empty source_indices is technically valid at the type level."""
    m = MergedKLine(high=10.0, low=5.0, timestamp="20250101", source_indices=())
    assert m.source_indices == ()


# ── Extreme ───────────────────────────────────────────────


def test_merged_kline_many_sources() -> None:
    indices = tuple(range(100))
    m = MergedKLine(high=10.0, low=5.0, timestamp="20250101", source_indices=indices)
    assert len(m.source_indices) == 100


def test_merged_kline_large_values() -> None:
    m = MergedKLine(high=1e15, low=1e-15, timestamp="20250101", source_indices=(0,))
    assert m.high == 1e15


# ── Immutability ──────────────────────────────────────────


def test_merged_kline_frozen() -> None:
    m = MergedKLine(high=10.0, low=5.0, timestamp="20250101", source_indices=(0,))
    with pytest.raises(AttributeError):
        m.high = 20.0  # type: ignore[misc]
    with pytest.raises(AttributeError):
        m.source_indices = (1, 2)  # type: ignore[misc]
