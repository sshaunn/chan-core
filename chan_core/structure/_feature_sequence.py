"""Feature sequence (特征序列) construction and fractal detection.

Implements S04-S06: feature sequence used only inside segments,
Type1End / Type2End termination, and t_extreme.
"""

from dataclasses import dataclass

from chan_core.common.math_utils import overlap
from chan_core.common.types import Direction
from chan_core.structure._pen import Pen


@dataclass(frozen=True)
class FeatureElement:
    """A virtual K-line representing one or more opposite-direction pens.

    Fields:
        high:        highest price across all source pens
        low:         lowest price across all source pens
        source_pens: the pen(s) merged into this element
    """

    high: float
    low: float
    source_pens: tuple[Pen, ...]

    @property
    def interval(self) -> tuple[float, float]:
        return (self.low, self.high)


def build_feature_sequence(
    pens: list[Pen], segment_direction: Direction
) -> list[FeatureElement]:
    """Extract opposite-direction pens as feature elements.

    For an UP segment, the feature sequence consists of DOWN pens.
    For a DOWN segment, the feature sequence consists of UP pens.
    """
    opposite = Direction.DOWN if segment_direction == Direction.UP else Direction.UP
    result: list[FeatureElement] = []
    for p in pens:
        if p.direction == opposite:
            result.append(
                FeatureElement(high=p.high, low=p.low, source_pens=(p,))
            )
    return result


def _has_inclusion_fe(a: FeatureElement, b: FeatureElement) -> bool:
    """Check inclusion between two feature elements (same rule as §4.2)."""
    return (a.high >= b.high and a.low <= b.low) or (
        b.high >= a.high and b.low <= a.low
    )


def _get_direction_fe(
    current: FeatureElement, prev: FeatureElement | None
) -> Direction:
    """Determine merge direction for feature elements."""
    if prev is None:
        return Direction.UP
    if current.high >= prev.high:
        return Direction.UP
    if current.low <= prev.low:
        return Direction.DOWN
    return Direction.UP


def _merge_two_fe(
    a: FeatureElement, b: FeatureElement, direction: Direction
) -> FeatureElement:
    """Merge two feature elements with inclusion (same rule as §4.4)."""
    if direction == Direction.UP:
        new_high = max(a.high, b.high)
        new_low = max(a.low, b.low)
    else:
        new_high = min(a.high, b.high)
        new_low = min(a.low, b.low)
    return FeatureElement(
        high=new_high,
        low=new_low,
        source_pens=a.source_pens + b.source_pens,
    )


def merge_feature_sequence(
    elements: list[FeatureElement],
) -> list[FeatureElement]:
    """Apply inclusion merge to a feature sequence (single-pass left-to-right).

    Same rules as §4.2-4.4 but applied to FeatureElement virtual K-lines.
    """
    if not elements:
        return []

    result: list[FeatureElement] = [elements[0]]

    for elem in elements[1:]:
        current = result[-1]
        if _has_inclusion_fe(current, elem):
            prev = result[-2] if len(result) >= 2 else None
            direction = _get_direction_fe(current, prev)
            merged = _merge_two_fe(current, elem, direction)
            result[-1] = merged
        else:
            result.append(elem)

    return result


def check_top_fseq(seq: list[FeatureElement], j: int) -> bool:
    """Check if position j in the merged feature sequence forms a top fractal.

    Strict inequalities on all four conditions (same as §5.1 / §7.3).
    """
    if j < 1 or j >= len(seq) - 1:
        return False
    left, mid, right = seq[j - 1], seq[j], seq[j + 1]
    return (
        mid.high > left.high
        and mid.high > right.high
        and mid.low > left.low
        and mid.low > right.low
    )


def check_bot_fseq(seq: list[FeatureElement], j: int) -> bool:
    """Check if position j in the merged feature sequence forms a bottom fractal.

    Strict inequalities on all four conditions (same as §5.2 / §7.3).
    """
    if j < 1 or j >= len(seq) - 1:
        return False
    left, mid, right = seq[j - 1], seq[j], seq[j + 1]
    return (
        mid.low < left.low
        and mid.low < right.low
        and mid.high < left.high
        and mid.high < right.high
    )


# ═══════════════════════════════════════════════════════════
#  Type1End / Type2End
# ═══════════════════════════════════════════════════════════


def find_t_extreme(element: FeatureElement, direction: Direction) -> str:
    """Find the extreme-value time anchor within a merged feature element.

    For UP direction: find the pen with max high → return its end timestamp.
    For DOWN direction: find the pen with min low → return its end timestamp.
    Tie-break: multiple pens with same extreme → take earliest t_end.
    """
    pens = element.source_pens
    if direction == Direction.UP:
        extreme_val = max(p.high for p in pens)
        candidates = [p for p in pens if p.high == extreme_val]
    else:
        extreme_val = min(p.low for p in pens)
        candidates = [p for p in pens if p.low == extreme_val]

    # Tie-break: earliest t_end (end fractal's middle kline timestamp)
    best = min(candidates, key=lambda p: p.end.klines[1].timestamp)
    return best.end.klines[1].timestamp


def build_verification_sequence(
    all_pens: list[Pen],
    segment_direction: Direction,
    t_extreme_val: str,
) -> list[FeatureElement]:
    """Build the verification sequence D' for Type2End.

    For UP segment: collect UP pens whose start time > t_extreme,
    treat as virtual K-lines, apply inclusion merge.
    For DOWN segment: collect DOWN pens, same logic.
    """
    # Collect pens in the same direction as the segment, after t_extreme
    candidates: list[Pen] = []
    for p in all_pens:
        if p.direction != segment_direction:
            continue
        p_start_time = p.start.klines[1].timestamp
        if p_start_time > t_extreme_val:
            candidates.append(p)

    if not candidates:
        return []

    # Convert to FeatureElements and apply inclusion merge
    elements = [
        FeatureElement(high=p.high, low=p.low, source_pens=(p,))
        for p in candidates
    ]
    return merge_feature_sequence(elements)


def check_type1_end(
    pens: list[Pen], segment_direction: Direction
) -> float | None:
    """Check for Type1End termination.

    Returns the termination point (float) or None.
    """
    fseq = build_feature_sequence(pens, segment_direction)
    merged_fseq = merge_feature_sequence(fseq)

    if len(merged_fseq) < 3:
        return None

    # Which fractal type to look for in the feature sequence
    if segment_direction == Direction.UP:
        check_fn = check_top_fseq
    else:
        check_fn = check_bot_fseq

    for j in range(1, len(merged_fseq) - 1):
        if not check_fn(merged_fseq, j):
            continue
        # Check overlap between C'_{j-1} and C'_j
        prev_el, cur_el = merged_fseq[j - 1], merged_fseq[j]
        if overlap(prev_el.low, prev_el.high, cur_el.low, cur_el.high):
            # Type1End found
            if segment_direction == Direction.UP:
                return cur_el.high
            else:
                return cur_el.low

    return None


def check_type2_end(
    pens: list[Pen], segment_direction: Direction
) -> float | None:
    """Check for Type2End termination.

    Returns the termination point (float) or None.
    """
    fseq = build_feature_sequence(pens, segment_direction)
    merged_fseq = merge_feature_sequence(fseq)

    if len(merged_fseq) < 3:
        return None

    if segment_direction == Direction.UP:
        check_fn = check_top_fseq
        verify_fn = check_bot_fseq  # Bot_FSeq_D for UP segment
        t_ext_dir = Direction.UP
    else:
        check_fn = check_bot_fseq
        verify_fn = check_top_fseq  # Top_FSeq_D for DOWN segment
        t_ext_dir = Direction.DOWN

    for j in range(1, len(merged_fseq) - 1):
        if not check_fn(merged_fseq, j):
            continue
        # Check NO overlap between C'_{j-1} and C'_j (gap / 缺口)
        prev_el, cur_el = merged_fseq[j - 1], merged_fseq[j]
        if overlap(prev_el.low, prev_el.high, cur_el.low, cur_el.high):
            continue  # This would be Type1End territory

        # Compute t_extreme from C'_j
        t_ext = find_t_extreme(cur_el, t_ext_dir)

        # Build verification sequence
        d_prime = build_verification_sequence(pens, segment_direction, t_ext)

        if len(d_prime) < 3:
            continue

        # Check for reverse fractal in verification sequence
        for r in range(1, len(d_prime) - 1):
            if verify_fn(d_prime, r):
                # Type2End confirmed
                if segment_direction == Direction.UP:
                    return cur_el.high
                else:
                    return cur_el.low

    return None
