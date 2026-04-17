"""Structure completion (S11–S12).

See `structure/README.md` S11–S12 for the full specification.

Level hierarchy:
  L0: pens → L0 pivots; L0 trend = segment; L0 complete = SegState==CONFIRMED
  L1: confirmed segments → L1 pivots; L1 complete = ExitSeq + i* over segments
  Lk: L(k-1) completed trends → Lk pivots; same ExitSeq + i* formula
"""

from __future__ import annotations

from typing import Sequence

from chan_core.common.math_utils import strict_overlap
from chan_core.common.protocols import SubTrendLike
from chan_core.common.types import SegmentState
from chan_core.engine import CompletionTrace, PivotSnapshot, SegmentSnapshot
from chan_core.structure._pivot import PivotBuilder, check_extension


def build_exit_sequence(
    pivot: PivotSnapshot,
    sub_trends: Sequence[SubTrendLike],
) -> list[SubTrendLike]:
    """Build the exit sequence ExitSeq(Z_last).

    Collect sub-trends that come after the pivot AND do not overlap
    the pivot's core interval [ZD, ZG].

    The first element must satisfy the leave condition, and all
    subsequent elements are collected in time order.
    """
    from chan_core.structure._pen import Pen
    from chan_core.engine import SegmentSnapshot

    result: list[SubTrendLike] = []
    found_leave = False

    for st in sub_trends:
        # Get start time of this sub-trend
        if isinstance(st, Pen):
            st_start = st.start.klines[1].timestamp
        elif isinstance(st, SegmentSnapshot):
            st_start = st.pens[0].start.klines[1].timestamp
        else:
            continue

        # Must be after the pivot's exit time
        if st_start <= pivot.exit_time:
            continue

        if not found_leave:
            # First element must be a leave (no overlap with [ZD, ZG])
            from chan_core.common.math_utils import overlap as _overlap

            if _overlap(st.low, st.high, pivot.zd, pivot.zg):
                continue  # Still extending, not a leave
            found_leave = True

        result.append(st)

    return result


def find_i_star(exit_seq: list[SubTrendLike]) -> int | None:
    """Find i* = first index where three consecutive elements form a new pivot.

    i* = min{i ∈ [0, n-3] : strict_overlap of three elements}
    (using 0-based indexing; spec uses 1-based)
    """
    n = len(exit_seq)
    if n < 3:
        return None

    for i in range(n - 2):
        w1, w2, w3 = exit_seq[i], exit_seq[i + 1], exit_seq[i + 2]
        zg = min(w1.high, w2.high, w3.high)
        zd = max(w1.low, w2.low, w3.low)
        if zd < zg:  # strict inequality → new pivot forms
            return i

    return None


def structure_complete_l0(segment: SegmentSnapshot) -> bool:
    """L0 structure_complete: a segment is complete iff CONFIRMED.

    §12.2: structure_complete_L0(T) ⟺ SegState(T) = CONFIRMED.
    L0 trend = segment; no pivot/ExitSeq needed at this level.
    """
    return segment.state == SegmentState.CONFIRMED


def structure_complete_by_pivot(
    pivots: list[PivotBuilder],
    sub_trends: Sequence[SubTrendLike],
) -> CompletionTrace:
    """Generic structure_complete via pivot ExitSeq + i* (for L1+).

    Used at L1 (sub_trends = confirmed segments) and higher levels.
    Checks whether the last pivot's exit sequence forms a new pivot.
    """
    if not pivots:
        return CompletionTrace(
            exit_seq_ids=(),
            i_star=None,
            t_end=None,
            awaiting_new_pivot=False,
        )

    last_pivot = pivots[-1].to_snapshot()
    exit_seq = build_exit_sequence(last_pivot, sub_trends)

    exit_ids = tuple(
        _get_id(st) for st in exit_seq
    )

    i_star = find_i_star(exit_seq)

    t_end: str | None = None
    if i_star is not None:
        w_i_star = exit_seq[i_star]
        from chan_core.structure._pen import Pen

        if isinstance(w_i_star, Pen):
            w_start_time = w_i_star.start.klines[1].timestamp
        elif isinstance(w_i_star, SegmentSnapshot):
            w_start_time = w_i_star.pens[0].start.klines[1].timestamp
        else:
            w_start_time = ""

        pred_end_times: list[str] = []
        for st in sub_trends:
            if isinstance(st, Pen):
                st_end = st.end.klines[1].timestamp
            elif isinstance(st, SegmentSnapshot):
                st_end = st.pens[-1].end.klines[1].timestamp
            else:
                continue
            if st_end < w_start_time:
                pred_end_times.append(st_end)

        if pred_end_times:
            t_end = max(pred_end_times)

    awaiting = len(exit_seq) > 0 and i_star is None

    return CompletionTrace(
        exit_seq_ids=exit_ids,
        i_star=i_star,
        t_end=t_end,
        awaiting_new_pivot=awaiting,
    )


def is_awaiting_new_pivot(trace: CompletionTrace) -> bool:
    """Check if the structure is in the awaiting-new-pivot observation state."""
    return trace.awaiting_new_pivot


def _get_id(st: SubTrendLike) -> str:
    """Generate an identifier string for a sub-trend."""
    from chan_core.structure._pen import Pen
    from chan_core.engine import SegmentSnapshot

    if isinstance(st, Pen):
        return f"Pen({st.start.value}->{st.end.value})"
    if isinstance(st, SegmentSnapshot):
        return f"Seg({st.low}->{st.high})"
    return f"Unknown({st.low}->{st.high})"
