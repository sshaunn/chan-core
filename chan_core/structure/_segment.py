"""Segment builder (three-stage recursion + absorption extension).

See `structure/README.md` S04–S06 for the full specification.
Book references: §6.1–§6.3.
"""

from __future__ import annotations

from chan_core.common.math_utils import overlap
from chan_core.common.types import Direction, SegmentState
from chan_core.engine import SegmentSnapshot
from chan_core.structure._feature_sequence import (
    EigenFX,
    EndType,
    map_end_pen_idx,
)
from chan_core.structure._pen import Pen


# ═══════════════════════════════════════════════════════════
#  Primitives
# ═══════════════════════════════════════════════════════════


def _opposite(d: Direction) -> Direction:
    return Direction.DOWN if d == Direction.UP else Direction.UP


def _first_three_overlap(pens: list[Pen], i: int) -> bool:
    """§6.1.1 rule A2: I(pens[i]) ∩ I(pens[i+2]) ≠ ∅."""
    if i + 2 >= len(pens):
        return False
    p0, p2 = pens[i], pens[i + 2]
    return overlap(p0.low, p0.high, p2.low, p2.high)


def _direction_dominant(seg_pens: list[Pen], direction: Direction) -> bool:
    """§6.1.1 + 78 课: segment trajectory must align with direction.

    UP needs `end > start`; DOWN needs `end < start`.
    """
    if not seg_pens:
        return False
    start_val = seg_pens[0].start.value
    end_val = seg_pens[-1].end.value
    if direction == Direction.UP:
        return end_val > start_val
    return end_val < start_val


def _exceeds(candidate: float, baseline: float, direction: Direction) -> bool:
    """Direction-aware strict comparison."""
    if direction == Direction.UP:
        return candidate > baseline
    return candidate < baseline


def _find_pen_index(pens: list[Pen], target: Pen) -> int | None:
    for i, p in enumerate(pens):
        if p is target:
            return i
    return None


# ═══════════════════════════════════════════════════════════
#  Stage A — Extreme-price fallback (§6.3.4 case 1)
# ═══════════════════════════════════════════════════════════


def _scan_price_extremes(
    pens: list[Pen], start: int, end: int
) -> list[tuple[int, str]]:
    """Scan the window for the most-extreme TOP pen and BOT pen.

    Returns (pen_idx, "TOP" | "BOT") pairs in time order (at most 2 entries).
    """
    if start >= end or end >= len(pens):
        return []

    max_top_val = -float("inf")
    max_top_pen_idx = -1
    min_bot_val = float("inf")
    min_bot_pen_idx = -1

    for global_idx in range(start, end + 1):
        p = pens[global_idx]
        end_val = p.end.value
        if p.direction == Direction.UP:
            if end_val > max_top_val:
                max_top_val = end_val
                max_top_pen_idx = global_idx
        else:
            if end_val < min_bot_val:
                min_bot_val = end_val
                min_bot_pen_idx = global_idx

    out: list[tuple[int, str]] = []
    if max_top_pen_idx >= 0:
        out.append((max_top_pen_idx, "TOP"))
    if min_bot_pen_idx >= 0:
        out.append((min_bot_pen_idx, "BOT"))
    out.sort(key=lambda t: t[0])
    return out


def _check_iron_rules(
    pens: list[Pen],
    seg_start: int,
    seg_end: int,
    direction: Direction,
) -> bool:
    """§6.1.1 three iron rules + directional dominance."""
    if seg_end - seg_start + 1 < 3:
        return False
    if (seg_end - seg_start + 1) % 2 != 1:
        return False
    if pens[seg_start].direction != direction:
        return False
    if not _first_three_overlap(pens, seg_start):
        return False
    if not _direction_dominant(list(pens[seg_start : seg_end + 1]), direction):
        return False
    return True


def _identify_by_extreme(
    pens: list[Pen],
    tail_start: int,
    expected_direction: Direction | None,
) -> SegmentSnapshot | None:
    """Stage A fallback: anchor segment endpoint at the window's extreme pen,
    then re-verify with iron rules (§6.3.4 case 1).
    """
    if tail_start + 2 >= len(pens):
        return None

    direction = pens[tail_start].direction
    if expected_direction is not None and direction != expected_direction:
        return None

    if not _first_three_overlap(pens, tail_start):
        return None

    extremes = _scan_price_extremes(pens, tail_start, len(pens) - 1)
    if not extremes:
        return None

    target_type = "TOP" if direction == Direction.UP else "BOT"
    candidates = [(idx, t) for idx, t in extremes if t == target_type]
    if not candidates:
        return None

    anchor_pen_idx, _ = candidates[0]
    if not _check_iron_rules(pens, tail_start, anchor_pen_idx, direction):
        return None

    seg_pens = tuple(pens[tail_start : anchor_pen_idx + 1])
    return SegmentSnapshot(
        pens=seg_pens,
        direction=direction,
        state=SegmentState.CONFIRMED,
        high=max(p.high for p in seg_pens),
        low=min(p.low for p in seg_pens),
        end_price=seg_pens[-1].end.value,
        end_type=EndType.EXTREME.value,
    )


# ═══════════════════════════════════════════════════════════
#  Constructive fallback — TENTATIVE (§6.1.1 "3-pen segment")
# ═══════════════════════════════════════════════════════════


def _tentative_tail_segment(
    pens: list[Pen],
    tail_start: int,
    expected_direction: Direction | None,
) -> SegmentSnapshot | None:
    """Last-resort fallback: longest odd-length chain satisfying A2 + dominance.

    Emits state=BUILDING, end_type=TENTATIVE for tail-end transparency.
    """
    if tail_start + 2 >= len(pens):
        return None

    direction = pens[tail_start].direction
    if expected_direction is not None and direction != expected_direction:
        return None

    if not _first_three_overlap(pens, tail_start):
        return None

    remaining = len(pens) - tail_start
    max_len = remaining if remaining % 2 == 1 else remaining - 1
    for seg_len in range(max_len, 2, -2):
        end_idx = tail_start + seg_len - 1
        seg_pens_list = list(pens[tail_start : end_idx + 1])
        if not _direction_dominant(seg_pens_list, direction):
            continue
        seg_pens = tuple(seg_pens_list)
        return SegmentSnapshot(
            pens=seg_pens,
            direction=direction,
            state=SegmentState.BUILDING,
            high=max(p.high for p in seg_pens),
            low=min(p.low for p in seg_pens),
            end_price=seg_pens[-1].end.value,
            end_type=EndType.TENTATIVE.value,
        )
    return None


# ═══════════════════════════════════════════════════════════
#  Stage B/C — Feature sequence method (EigenFX streaming)
# ═══════════════════════════════════════════════════════════


def _identify_one_segment(
    pens: list[Pen], i_start: int, direction: Direction
) -> tuple[int, float, EndType] | None:
    """Stream pens[i_start+1:] through EigenFX; return first-hit or None."""
    efx = EigenFX(direction)
    for k in range(i_start + 1, len(pens)):
        result = efx.add(pens[k])
        if result is None:
            continue
        end_idx = map_end_pen_idx(pens, i_start, result, direction, efx.F)
        if end_idx is None:
            continue
        return (end_idx, result.end_price, result.end_type)
    return None


# ═══════════════════════════════════════════════════════════
#  Pass 1 — Three-stage recursive identification
# ═══════════════════════════════════════════════════════════


def _build_segments_pass1(pens: list[Pen]) -> list[SegmentSnapshot]:
    """Pass 1: three-stage identification without Pass 2 extension."""
    if len(pens) < 3:
        return []

    segments: list[SegmentSnapshot] = []

    # Phase 1: first segment — flexible starting point (§6.1.2).
    first_end_idx: int | None = None
    first_dir: Direction | None = None
    for i in range(len(pens) - 2):
        if not _first_three_overlap(pens, i):
            continue
        direction = pens[i].direction

        # Stage B/C
        result = _identify_one_segment(pens, i, direction)
        if result is not None:
            end_idx, end_price, end_type = result
            seg_pens_list = list(pens[i : end_idx + 1])
            if _direction_dominant(seg_pens_list, direction):
                seg_pens = tuple(seg_pens_list)
                segments.append(
                    SegmentSnapshot(
                        pens=seg_pens,
                        direction=direction,
                        state=SegmentState.CONFIRMED,
                        high=max(p.high for p in seg_pens),
                        low=min(p.low for p in seg_pens),
                        end_price=end_price,
                        end_type=end_type.value,
                    )
                )
                first_end_idx = end_idx
                first_dir = direction
                break

    if first_end_idx is None:
        # Stage A fallback, then constructive fallback.
        for i0 in range(len(pens) - 2):
            if not _first_three_overlap(pens, i0):
                continue
            extreme = _identify_by_extreme(pens, i0, None)
            if extreme is not None:
                segments.append(extreme)
                first_end_idx = next(
                    idx for idx, p in enumerate(pens)
                    if p is extreme.pens[-1]
                )
                first_dir = extreme.direction
                break
            tent = _tentative_tail_segment(pens, i0, None)
            if tent is not None:
                segments.append(tent)
            return segments
        if first_end_idx is None:
            return segments

    # Phase 2: subsequent segments — strict adjacency (§6.1.3).
    i = first_end_idx + 1
    prev_dir = first_dir
    while i + 2 < len(pens):
        expected_dir = _opposite(prev_dir)

        if pens[i].direction != expected_dir:
            break
        if not _first_three_overlap(pens, i):
            break

        result = _identify_one_segment(pens, i, expected_dir)
        if result is None:
            extreme = _identify_by_extreme(pens, i, expected_dir)
            if extreme is not None:
                segments.append(extreme)
                ext_end_idx = next(
                    idx for idx, p in enumerate(pens)
                    if p is extreme.pens[-1]
                )
                prev_dir = expected_dir
                i = ext_end_idx + 1
                continue
            tent = _tentative_tail_segment(pens, i, expected_dir)
            if tent is not None:
                segments.append(tent)
            break

        end_idx, end_price, end_type = result
        seg_pens_list = list(pens[i : end_idx + 1])
        if not _direction_dominant(seg_pens_list, expected_dir):
            extreme = _identify_by_extreme(pens, i, expected_dir)
            if extreme is not None:
                segments.append(extreme)
                ext_end_idx = next(
                    idx for idx, p in enumerate(pens)
                    if p is extreme.pens[-1]
                )
                prev_dir = expected_dir
                i = ext_end_idx + 1
                continue
            tent = _tentative_tail_segment(pens, i, expected_dir)
            if tent is not None:
                segments.append(tent)
            break

        seg_pens = tuple(seg_pens_list)
        segments.append(
            SegmentSnapshot(
                pens=seg_pens,
                direction=expected_dir,
                state=SegmentState.CONFIRMED,
                high=max(p.high for p in seg_pens),
                low=min(p.low for p in seg_pens),
                end_price=end_price,
                end_type=end_type.value,
            )
        )
        prev_dir = expected_dir
        i = end_idx + 1

    return segments


# ═══════════════════════════════════════════════════════════
#  Pass 2 — Segment extension (§6.3.3 "gap closed → segment extends")
# ═══════════════════════════════════════════════════════════


def _try_extend_pair(
    all_pens: list[Pen],
    seg_k: SegmentSnapshot,
    seg_kp1: SegmentSnapshot,
) -> tuple[list[Pen], int] | None:
    """Check if seg_{k+1} contains a CONFIRMED reverse segment to absorb.

    Only `_identify_one_segment` results (TYPE1/TYPE2) qualify. The reverse
    segment's endpoint must strictly exceed seg_k's endpoint in seg_k's
    direction to justify absorption.
    """
    kp1_pens = list(seg_kp1.pens)
    if len(kp1_pens) < 4:
        return None

    sub_pens = kp1_pens[1:]
    if not sub_pens or sub_pens[0].direction != seg_k.direction:
        return None
    if not _first_three_overlap(sub_pens, 0):
        return None

    rev_result = _identify_one_segment(sub_pens, 0, seg_k.direction)
    if rev_result is None:
        return None
    rev_end_idx, _, _ = rev_result
    rev_seg_pens = sub_pens[: rev_end_idx + 1]

    if not _direction_dominant(rev_seg_pens, seg_k.direction):
        return None

    rev_end_val = rev_seg_pens[-1].end.value
    seg_k_end_val = seg_k.pens[-1].end.value
    if not _exceeds(rev_end_val, seg_k_end_val, seg_k.direction):
        return None

    new_pens = list(seg_k.pens) + [kp1_pens[0]] + list(rev_seg_pens)
    if len(new_pens) < 3 or len(new_pens) % 2 != 1:
        return None
    if not _direction_dominant(new_pens, seg_k.direction):
        return None

    last_pen = new_pens[-1]
    last_global = _find_pen_index(all_pens, last_pen)
    if last_global is None:
        return None

    return (new_pens, last_global)


def _build_strict_tail(
    tail_pens: list[Pen], required_first_dir: Direction
) -> list[SegmentSnapshot]:
    """Re-identify the tail with the first segment's direction fixed.

    Used after Pass 2 absorption to keep adjacent-segment direction alternation
    (no flexible starting point here).
    """
    out: list[SegmentSnapshot] = []
    if not tail_pens:
        return out

    if tail_pens[0].direction != required_first_dir:
        tent = _tentative_tail_segment(tail_pens, 0, required_first_dir)
        if tent is not None:
            out.append(tent)
        return out

    if not _first_three_overlap(tail_pens, 0):
        tent = _tentative_tail_segment(tail_pens, 0, required_first_dir)
        if tent is not None:
            out.append(tent)
        return out

    result = _identify_one_segment(tail_pens, 0, required_first_dir)
    if result is None:
        tent = _tentative_tail_segment(tail_pens, 0, required_first_dir)
        if tent is not None:
            out.append(tent)
        return out

    end_idx, end_price, end_type = result
    seg_pens_list = list(tail_pens[: end_idx + 1])
    if not _direction_dominant(seg_pens_list, required_first_dir):
        tent = _tentative_tail_segment(tail_pens, 0, required_first_dir)
        if tent is not None:
            out.append(tent)
        return out

    seg_pens = tuple(seg_pens_list)
    out.append(
        SegmentSnapshot(
            pens=seg_pens,
            direction=required_first_dir,
            state=SegmentState.CONFIRMED,
            high=max(p.high for p in seg_pens),
            low=min(p.low for p in seg_pens),
            end_price=end_price,
            end_type=end_type.value,
        )
    )
    rest = tail_pens[end_idx + 1 :]
    sub = _build_strict_tail(rest, _opposite(required_first_dir))
    out.extend(sub)
    return out


# ═══════════════════════════════════════════════════════════
#  Entry point — build_segments (Pass 1 + Pass 2)
# ═══════════════════════════════════════════════════════════


def build_segments(pens: list[Pen]) -> list[SegmentSnapshot]:
    """Build the segment sequence from a pen list.

    Pass 1: three-stage identification (feature sequence → extreme → tentative).
    Pass 2: absorption extension per §6.3.3.

    CONFIRMED segments carry end_type ∈ {TYPE1, TYPE2, EXTREME, EXTENDED};
    TENTATIVE segments (state=BUILDING) are tail-end only and not consumed
    by downstream layers.
    """
    if len(pens) < 3:
        return []

    segments = _build_segments_pass1(pens)
    if not segments:
        return []

    k = 0
    while k < len(segments) - 1:
        seg_k = segments[k]
        seg_kp1 = segments[k + 1]
        ext = _try_extend_pair(pens, seg_k, seg_kp1)
        if ext is None:
            k += 1
            continue
        new_pens, last_global = ext

        new_seg_k = SegmentSnapshot(
            pens=tuple(new_pens),
            direction=seg_k.direction,
            state=SegmentState.CONFIRMED,
            high=max(p.high for p in new_pens),
            low=min(p.low for p in new_pens),
            end_price=new_pens[-1].end.value,
            end_type=EndType.EXTENDED.value,
        )

        tail_pens = list(pens[last_global + 1 :])
        tail_segments = _build_strict_tail(tail_pens, _opposite(new_seg_k.direction))

        segments = segments[:k] + [new_seg_k] + tail_segments
        # Keep k fixed to allow chained absorption.

    return segments


__all__ = ["build_segments"]
