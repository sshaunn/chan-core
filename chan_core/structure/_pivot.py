"""Pivot builder, extension/leave logic, and search (S07–S09).

See `structure/README.md` S07–S09 for the full specification.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from typing import Sequence

from chan_core.common.math_utils import overlap, strict_overlap
from chan_core.common.protocols import SubTrendLike
from chan_core.common.types import Direction
from chan_core.engine import PivotSnapshot


@dataclass
class PivotBuilder:
    """Mutable pivot under construction.

    ZD/ZG are set at creation and never updated.
    DD/GG and components are updated on extension.
    """

    zd: float
    zg: float
    dd: float
    gg: float
    components: list[SubTrendLike]
    entry_time: str
    exit_time: str

    def to_snapshot(self) -> PivotSnapshot:
        return PivotSnapshot(
            zd=self.zd,
            zg=self.zg,
            dd=self.dd,
            gg=self.gg,
            components=tuple(self.components),
            entry_time=self.entry_time,
            exit_time=self.exit_time,
        )


def _get_time_start(s: SubTrendLike) -> str:
    """Get start timestamp from a SubTrendLike (Pen or SegmentSnapshot)."""
    from chan_core.engine import SegmentSnapshot
    from chan_core.structure._pen import Pen

    if isinstance(s, Pen):
        return s.start.klines[1].timestamp
    if isinstance(s, SegmentSnapshot):
        return s.pens[0].start.klines[1].timestamp
    raise TypeError(f"Unsupported SubTrendLike type: {type(s)}")


def _get_time_end(s: SubTrendLike) -> str:
    """Get end timestamp from a SubTrendLike."""
    from chan_core.engine import SegmentSnapshot
    from chan_core.structure._pen import Pen

    if isinstance(s, Pen):
        return s.end.klines[1].timestamp
    if isinstance(s, SegmentSnapshot):
        return s.pens[-1].end.klines[1].timestamp
    raise TypeError(f"Unsupported SubTrendLike type: {type(s)}")


def try_form_pivot(
    p1: SubTrendLike, p2: SubTrendLike, p3: SubTrendLike
) -> PivotBuilder | None:
    """Try to form a pivot from three consecutive sub-trends.

    ZG = min(highs), ZD = max(lows).
    Pivot forms iff ZD < ZG (strict).
    """
    zg = min(p1.high, p2.high, p3.high)
    zd = max(p1.low, p2.low, p3.low)

    if not (zd < zg):
        return None

    gg = max(p1.high, p2.high, p3.high)
    dd = min(p1.low, p2.low, p3.low)

    return PivotBuilder(
        zd=zd,
        zg=zg,
        dd=dd,
        gg=gg,
        components=[p1, p2, p3],
        entry_time=_get_time_start(p1),
        exit_time=_get_time_end(p3),
    )


def check_extension(pen: SubTrendLike, pivot: PivotBuilder) -> bool:
    """Check if a pen extends the pivot: [pen.low, pen.high] ∩ [ZD, ZG] ≠ ∅."""
    return overlap(pen.low, pen.high, pivot.zd, pivot.zg)


def apply_extension(pen: SubTrendLike, pivot: PivotBuilder) -> None:
    """Apply extension: update GG/DD/components, keep ZD/ZG unchanged."""
    pivot.gg = max(pivot.gg, pen.high)
    pivot.dd = min(pivot.dd, pen.low)
    pivot.components.append(pen)
    pivot.exit_time = _get_time_end(pen)


def check_leave(
    pen: SubTrendLike, pivot: PivotBuilder
) -> Direction | None:
    """Check if a pen leaves the pivot.

    Returns Direction.UP if pen is above, Direction.DOWN if below,
    or None if it doesn't leave (extends).
    """
    if check_extension(pen, pivot):
        return None
    if pen.low > pivot.zg:
        return Direction.UP
    if pen.high < pivot.zd:
        return Direction.DOWN
    return None


def search_pivots(pens: Sequence[SubTrendLike]) -> list[PivotBuilder]:
    """Search for pivots in a pen/sub-trend sequence.

    The leave pen does not overlap [ZD, ZG] of the current pivot, so it
    belongs to the next structure. New search starts from the leave pen
    itself (it becomes the candidate first pen of the next pivot).
    """
    n = len(pens)
    pivots: list[PivotBuilder] = []
    i = 0

    while i <= n - 3:
        p1, p2, p3 = pens[i], pens[i + 1], pens[i + 2]
        pivot = try_form_pivot(p1, p2, p3)

        if pivot is None:
            i += 1
            continue

        # Pivot formed. Check extension/leave for subsequent pens.
        j = i + 3
        leave_idx: int | None = None

        while j < n:
            pj = pens[j]
            if check_extension(pj, pivot):
                apply_extension(pj, pivot)
                j += 1
            else:
                leave_idx = j
                break

        pivots.append(pivot)

        if leave_idx is None:
            break  # End of data

        # Leave pen belongs to next pivot's search window.
        i = leave_idx

    return pivots
