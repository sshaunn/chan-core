"""Trend classification (走势分类).

Implements S10: consolidation / up-trend / down-trend based on
pivot count and DD/GG relationships. Requires structure_complete.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from chan_core.common.types import TrendType
from chan_core.engine import CompletionTrace, PivotSnapshot, TrendSnapshot
from chan_core.structure._pivot import PivotBuilder


def classify_trend(
    pivots: list[PivotSnapshot], structure_complete: bool
) -> TrendType | None:
    """Classify a trend based on its pivot sequence.

    Returns None if structure_complete is False or no pivots exist.
    """
    if not structure_complete or not pivots:
        return None

    if len(pivots) == 1:
        return TrendType.CONSOLIDATION

    # Check if all adjacent pivots satisfy up-trend condition
    all_up = all(
        pivots[k + 1].dd > pivots[k].gg for k in range(len(pivots) - 1)
    )
    if all_up:
        return TrendType.UP_TREND

    # Check if all adjacent pivots satisfy down-trend condition
    all_down = all(
        pivots[k + 1].gg < pivots[k].dd for k in range(len(pivots) - 1)
    )
    if all_down:
        return TrendType.DOWN_TREND

    return None


@dataclass
class TrendBuilder:
    """Mutable trend under construction."""

    pivots: list[PivotBuilder]
    trend_type: TrendType | None = field(default=None)
    structure_complete: bool = field(default=False)

    def to_snapshot(self, completion: CompletionTrace) -> TrendSnapshot:
        return TrendSnapshot(
            pivots=tuple(p.to_snapshot() for p in self.pivots),
            trend_type=self.trend_type,
            structure_complete=self.structure_complete,
            completion=completion,
        )
