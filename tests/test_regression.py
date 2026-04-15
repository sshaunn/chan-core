"""Task 15: Regression tests and consistency checks.

Ensures that any future code changes do not break verified behavior.
"""

import csv
import os

import pytest

from chan_core import ChanEngine, RawKLine
from chan_core.common.types import Direction, FractalType, TrendType
from chan_core.engine import AnalysisResult
from chan_core.structure._merge import has_inclusion


def _load_csv(filename: str) -> list[RawKLine]:
    csv_path = os.path.join(
        os.path.dirname(__file__), "..", "doc", "cache", filename
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


def _analyze(filename: str) -> AnalysisResult:
    return ChanEngine().analyze(_load_csv(filename))


# ═══════════════════════════════════════════════════════════
#  Structural invariants — must hold for ANY dataset
# ═══════════════════════════════════════════════════════════


@pytest.mark.parametrize("filename", [
    "300811.SZ_20250411_20260410.csv",
    "300812.SZ_20250411_20260410.csv",
])
class TestStructuralInvariants:

    def test_zero_inclusion_post_merge(self, filename: str) -> None:
        """No adjacent merged bars have inclusion."""
        result = _analyze(filename)
        for i in range(len(result.merged_klines) - 1):
            assert not has_inclusion(
                result.merged_klines[i], result.merged_klines[i + 1]
            ), f"Inclusion at index {i}"

    def test_source_indices_complete(self, filename: str) -> None:
        """Every raw index appears exactly once across all merged bars."""
        result = _analyze(filename)
        raw_count = sum(len(m.source_indices) for m in result.merged_klines)
        all_indices: list[int] = []
        for m in result.merged_klines:
            all_indices.extend(m.source_indices)
        assert sorted(all_indices) == list(range(raw_count))

    def test_pen_zero_gap(self, filename: str) -> None:
        """pen[k].end == pen[k+1].start (zero-gap)."""
        result = _analyze(filename)
        for i in range(len(result.pens) - 1):
            assert result.pens[i].end is result.pens[i + 1].start

    def test_pen_direction_alternates(self, filename: str) -> None:
        """Adjacent pens alternate direction."""
        result = _analyze(filename)
        for i in range(len(result.pens) - 1):
            assert result.pens[i].direction != result.pens[i + 1].direction

    def test_fractals_strict_inequality(self, filename: str) -> None:
        """All fractals satisfy strict inequality on all four conditions."""
        result = _analyze(filename)
        for f in result.fractals:
            left, mid, right = f.klines
            if f.type == FractalType.TOP:
                assert mid.high > left.high
                assert mid.high > right.high
                assert mid.low > left.low
                assert mid.low > right.low
            else:
                assert mid.low < left.low
                assert mid.low < right.low
                assert mid.high < left.high
                assert mid.high < right.high

    def test_pivot_four_boundary_invariant(self, filename: str) -> None:
        """DD ≤ ZD < ZG ≤ GG for all pivots."""
        result = _analyze(filename)
        for p in result.pivots:
            assert p.dd <= p.zd < p.zg <= p.gg

    def test_pivot_zd_zg_strict(self, filename: str) -> None:
        """ZD < ZG (strict inequality) for all pivots."""
        result = _analyze(filename)
        for p in result.pivots:
            assert p.zd < p.zg


# ═══════════════════════════════════════════════════════════
#  Fixed output regression — exact values
# ═══════════════════════════════════════════════════════════


class TestRegression300811:
    """Exact output values for 300811.SZ — any change must be intentional."""

    @pytest.fixture(scope="class")
    def result(self) -> AnalysisResult:
        return _analyze("300811.SZ_20250411_20260410.csv")

    def test_merged_count(self, result: AnalysisResult) -> None:
        assert len(result.merged_klines) == 181

    def test_fractal_count(self, result: AnalysisResult) -> None:
        assert len(result.fractals) == 84

    def test_pen_count(self, result: AnalysisResult) -> None:
        assert len(result.pens) == 17

    def test_pivot_count(self, result: AnalysisResult) -> None:
        assert len(result.pivots) == 2

    def test_trend_count(self, result: AnalysisResult) -> None:
        assert len(result.trends) == 2

    def test_t1_complete(self, result: AnalysisResult) -> None:
        assert result.trends[0].structure_complete is True

    def test_t1_consolidation(self, result: AnalysisResult) -> None:
        assert result.trends[0].trend_type == TrendType.CONSOLIDATION

    def test_t2_not_complete(self, result: AnalysisResult) -> None:
        assert result.trends[1].structure_complete is False

    def test_z0_zd(self, result: AnalysisResult) -> None:
        assert result.pivots[0].zd == pytest.approx(40.51, abs=0.01)

    def test_z0_zg(self, result: AnalysisResult) -> None:
        assert result.pivots[0].zg == pytest.approx(44.07, abs=0.01)

    def test_z1_zd(self, result: AnalysisResult) -> None:
        assert result.pivots[1].zd == pytest.approx(68.59, abs=0.01)

    def test_z1_zg(self, result: AnalysisResult) -> None:
        assert result.pivots[1].zg == pytest.approx(82.50, abs=0.01)

    def test_first_pen_values(self, result: AnalysisResult) -> None:
        p0 = result.pens[0]
        assert p0.start.value == pytest.approx(44.07, abs=0.01)
        assert p0.end.value == pytest.approx(39.98, abs=0.01)
        assert p0.direction == Direction.DOWN

    def test_last_pen_values(self, result: AnalysisResult) -> None:
        p16 = result.pens[16]
        assert p16.start.value == pytest.approx(81.96, abs=0.01)
        assert p16.end.value == pytest.approx(72.75, abs=0.01)
        assert p16.direction == Direction.DOWN
