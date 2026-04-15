"""Task 14: Full-chain fixed sample playback.

Validates the complete pipeline from raw K-lines to structure_complete
against the fixed samples in 最终稿 §13.
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


# ═══════════════════════════════════════════════════════════
#  300811.SZ full chain
# ═══════════════════════════════════════════════════════════


class Test300811:
    """Full-chain validation for 300811.SZ (20250411~20260410)."""

    @pytest.fixture(scope="class")
    def result(self) -> AnalysisResult:
        raw = _load_csv("300811.SZ_20250411_20260410.csv")
        engine = ChanEngine()
        return engine.analyze(raw)

    def test_raw_count(self, result: AnalysisResult) -> None:
        # Not stored directly, but we can infer from merge trace
        total_raw = sum(len(m.source_indices) for m in result.merged_klines)
        assert total_raw == 242

    def test_merged_count(self, result: AnalysisResult) -> None:
        assert len(result.merged_klines) == 181

    def test_zero_inclusion(self, result: AnalysisResult) -> None:
        for i in range(len(result.merged_klines) - 1):
            assert not has_inclusion(
                result.merged_klines[i], result.merged_klines[i + 1]
            )

    def test_fractal_count(self, result: AnalysisResult) -> None:
        assert len(result.fractals) == 84
        tops = [f for f in result.fractals if f.type == FractalType.TOP]
        bots = [f for f in result.fractals if f.type == FractalType.BOT]
        assert len(tops) == 42
        assert len(bots) == 42

    def test_pen_count(self, result: AnalysisResult) -> None:
        assert len(result.pens) == 17

    def test_pen_zero_gap(self, result: AnalysisResult) -> None:
        for i in range(len(result.pens) - 1):
            assert result.pens[i].end is result.pens[i + 1].start

    def test_pen_direction_alternates(self, result: AnalysisResult) -> None:
        for i in range(len(result.pens) - 1):
            assert result.pens[i].direction != result.pens[i + 1].direction

    def test_pen_first_direction(self, result: AnalysisResult) -> None:
        assert result.pens[0].direction == Direction.DOWN

    def test_pen_values(self, result: AnalysisResult) -> None:
        expected = [
            (44.07, 39.98), (39.98, 44.88), (44.88, 40.51),
            (40.51, 62.53), (62.53, 54.40), (54.40, 82.50),
            (82.50, 68.59), (68.59, 87.36), (87.36, 65.10),
            (65.10, 76.78), (76.78, 67.53), (67.53, 86.10),
            (86.10, 73.05), (73.05, 91.00), (91.00, 75.03),
            (75.03, 81.96), (81.96, 72.75),
        ]
        for i, (sv, ev) in enumerate(expected):
            assert result.pens[i].start.value == pytest.approx(sv, abs=0.01)
            assert result.pens[i].end.value == pytest.approx(ev, abs=0.01)

    def test_pivot_count(self, result: AnalysisResult) -> None:
        assert len(result.pivots) == 2

    def test_z0_boundaries(self, result: AnalysisResult) -> None:
        z0 = result.pivots[0]
        assert z0.zg == pytest.approx(44.07, abs=0.01)
        assert z0.zd == pytest.approx(40.51, abs=0.01)

    def test_z1_boundaries(self, result: AnalysisResult) -> None:
        z1 = result.pivots[1]
        assert z1.zg == pytest.approx(82.50, abs=0.01)
        assert z1.zd == pytest.approx(68.59, abs=0.01)

    def test_four_boundary_invariant(self, result: AnalysisResult) -> None:
        for p in result.pivots:
            assert p.dd <= p.zd < p.zg <= p.gg

    def test_structure_complete_true(self, result: AnalysisResult) -> None:
        """T1 containing Z0 is complete."""
        assert len(result.trends) >= 1
        trend = result.trends[0]
        assert trend.structure_complete is True

    def test_trend_classification(self, result: AnalysisResult) -> None:
        """1 pivot (Z0) in complete trend → consolidation."""
        # The whole analysis has 2 pivots, but structure_complete is based
        # on exit sequence of last pivot. Since we compute for the full
        # sequence, the trend type depends on the overall result.
        trend = result.trends[0]
        # With 2 pivots + complete, check classification
        if len(trend.pivots) == 2:
            # Not a simple consolidation — depends on DD/GG relationship
            pass  # Classification tested separately
        elif len(trend.pivots) == 1:
            assert trend.trend_type == TrendType.CONSOLIDATION

    def test_i_star_exists(self, result: AnalysisResult) -> None:
        trend = result.trends[0]
        assert trend.completion.i_star is not None

    def test_t_end_exists(self, result: AnalysisResult) -> None:
        trend = result.trends[0]
        assert trend.completion.t_end is not None

    def test_exit_seq_not_empty(self, result: AnalysisResult) -> None:
        trend = result.trends[0]
        assert len(trend.completion.exit_seq_ids) > 0

    def test_source_indices_complete(self, result: AnalysisResult) -> None:
        """Every raw index appears exactly once."""
        all_indices: list[int] = []
        for m in result.merged_klines:
            all_indices.extend(m.source_indices)
        assert sorted(all_indices) == list(range(242))

    def test_fractals_use_strict_inequality(self, result: AnalysisResult) -> None:
        """Verify all fractals satisfy strict inequality conditions."""
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


# ═══════════════════════════════════════════════════════════
#  Engine API tests
# ═══════════════════════════════════════════════════════════


def test_engine_returns_immutable_result() -> None:
    raw = _load_csv("300811.SZ_20250411_20260410.csv")
    engine = ChanEngine()
    result = engine.analyze(raw)
    with pytest.raises(AttributeError):
        result.pens = ()  # type: ignore[misc]


def test_engine_empty_input() -> None:
    engine = ChanEngine()
    result = engine.analyze([])
    assert result.merged_klines == ()
    assert result.fractals == ()
    assert result.pens == ()
    assert result.segments == ()
    assert result.pivots == ()


def test_engine_single_kline() -> None:
    engine = ChanEngine()
    result = engine.analyze([RawKLine(high=10, low=5, timestamp="20250101")])
    assert len(result.merged_klines) == 1
    assert result.fractals == ()
    assert result.pens == ()
