"""Segment (线段) builder and state machine.

Implements S04-S06: segment formation, BUILDING/CONFIRMED states.
Builder is mutable internally; to_snapshot() produces frozen output.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from chan_core.common.math_utils import overlap
from chan_core.common.types import Direction, SegmentState
from chan_core.engine import SegmentSnapshot
from chan_core.structure._feature_sequence import check_type1_end, check_type2_end
from chan_core.structure._pen import Pen


def check_first_three_overlap(pens: list[Pen]) -> bool:
    """Check that the first and third pens have overlapping intervals.

    Required for segment formation: I(B_1) ∩ I(B_3) ≠ ∅.
    """
    if len(pens) < 3:
        return False
    p1, p3 = pens[0], pens[2]
    return overlap(p1.low, p1.high, p3.low, p3.high)


@dataclass
class SegmentBuilder:
    """Mutable segment under construction.

    State transitions: BUILDING → CONFIRMED (irreversible).
    Not exposed in public API — use to_snapshot().
    """

    pens: list[Pen]
    direction: Direction
    state: SegmentState = field(default=SegmentState.BUILDING)

    @property
    def pen_count(self) -> int:
        return len(self.pens)

    @property
    def high(self) -> float:
        return max(p.high for p in self.pens)

    @property
    def low(self) -> float:
        return min(p.low for p in self.pens)

    @property
    def interval(self) -> tuple[float, float]:
        return (self.low, self.high)

    def confirm(self) -> None:
        """Transition BUILDING → CONFIRMED. Irreversible."""
        if self.state == SegmentState.CONFIRMED:
            raise RuntimeError("Segment already confirmed")
        self.state = SegmentState.CONFIRMED

    def to_snapshot(self) -> SegmentSnapshot:
        """Produce a frozen snapshot of this segment."""
        return SegmentSnapshot(
            pens=tuple(self.pens),
            direction=self.direction,
            state=self.state,
            high=self.high,
            low=self.low,
        )


def _try_confirm_segment(builder: SegmentBuilder) -> bool:
    """Attempt to confirm a BUILDING segment via Type1End or Type2End.

    Returns True if confirmed, False otherwise.
    """
    if builder.pen_count < 3:
        return False

    # Try Type1End first
    t1 = check_type1_end(builder.pens, builder.direction)
    if t1 is not None:
        builder.confirm()
        return True

    # Try Type2End
    t2 = check_type2_end(builder.pens, builder.direction)
    if t2 is not None:
        builder.confirm()
        return True

    return False


def build_segments(pens: list[Pen]) -> list[SegmentSnapshot]:
    """Build confirmed segments from a pen sequence.

    Algorithm:
    1. Start a new segment candidate with first 3 pens (if they overlap).
    2. Grow the segment by adding pens one at a time.
    3. After each addition, check Type1End/Type2End.
    4. When confirmed, start scanning for the next segment from the
       pen following the last opposite-direction pen in the confirmed
       segment's feature sequence fractal.

    For simplicity and correctness, we use a greedy approach:
    grow the segment by adding 2 pens at a time (to maintain odd count),
    then check for termination.
    """
    if len(pens) < 3:
        return []

    segments: list[SegmentSnapshot] = []
    i = 0  # start index in pens

    while i <= len(pens) - 3:
        # Try to start a segment at position i
        first_three = pens[i : i + 3]
        if not check_first_three_overlap(first_three):
            i += 1
            continue

        # Segment direction = first pen's direction
        direction = pens[i].direction

        # Grow the segment, checking for termination at each odd pen count
        confirmed = False
        for end in range(i + 3, len(pens) + 1, 2):
            candidate_pens = pens[i:end]
            builder = SegmentBuilder(
                pens=list(candidate_pens),
                direction=direction,
            )
            if _try_confirm_segment(builder):
                segments.append(builder.to_snapshot())
                # Next segment starts from the last pen of this one's
                # termination region. We advance i to end - 1 to allow
                # overlap (the last pen of one segment can be the first
                # of the next).
                i = end - 1
                confirmed = True
                break

        if not confirmed:
            # Try with the full remaining pens (even count is ok for checking)
            candidate_pens = pens[i:]
            if len(candidate_pens) >= 3:
                builder = SegmentBuilder(
                    pens=list(candidate_pens),
                    direction=direction,
                )
                if _try_confirm_segment(builder):
                    segments.append(builder.to_snapshot())
            break

    return segments
