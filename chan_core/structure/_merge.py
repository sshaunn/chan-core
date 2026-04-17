"""K-line inclusion merge (S01).

Single-pass left-to-right, no backtracking.
See `structure/README.md` S01 for the full specification.
"""

from chan_core.common.kline import MergedKLine, RawKLine
from chan_core.common.types import Direction


def has_inclusion(a: MergedKLine, b: MergedKLine) -> bool:
    """Check whether two merged K-lines have an inclusion relationship.

    inc(a, b) ⟺ (a.high ≥ b.high ∧ a.low ≤ b.low)
              ∨ (b.high ≥ a.high ∧ b.low ≤ a.low)
    """
    return (a.high >= b.high and a.low <= b.low) or (
        b.high >= a.high and b.low <= a.low
    )


def get_merge_direction(
    current: MergedKLine, prev: MergedKLine | None
) -> Direction:
    """Determine merge direction based on the previous non-inclusive bar.

    If no previous bar exists (sequence start), default to UP.
    """
    if prev is None:
        return Direction.UP
    if current.high >= prev.high:
        return Direction.UP
    if current.low <= prev.low:
        return Direction.DOWN
    # current is strictly inside prev on both sides — should not happen
    # after inclusion merge, but default to UP as a safe fallback.
    return Direction.UP


def merge_two(
    a: MergedKLine, b: MergedKLine, direction: Direction
) -> MergedKLine:
    """Merge two K-lines that have an inclusion relationship.

    UP:   take max(highs), max(lows)
    DOWN: take min(highs), min(lows)
    """
    if direction == Direction.UP:
        new_high = max(a.high, b.high)
        new_low = max(a.low, b.low)
    else:
        new_high = min(a.high, b.high)
        new_low = min(a.low, b.low)

    return MergedKLine(
        high=new_high,
        low=new_low,
        timestamp=b.timestamp,
        source_indices=a.source_indices + b.source_indices,
    )


def merge_inclusive(klines: list[RawKLine]) -> list[MergedKLine]:
    """Single-pass left-to-right inclusion merge.

    Returns a list of MergedKLine with no adjacent inclusion pairs.
    Every raw bar index appears in exactly one MergedKLine.source_indices.
    """
    if not klines:
        return []

    # Seed: first raw bar becomes first merged bar.
    result: list[MergedKLine] = [
        MergedKLine(
            high=klines[0].high,
            low=klines[0].low,
            timestamp=klines[0].timestamp,
            source_indices=(0,),
        )
    ]

    for idx in range(1, len(klines)):
        raw = klines[idx]
        candidate = MergedKLine(
            high=raw.high,
            low=raw.low,
            timestamp=raw.timestamp,
            source_indices=(idx,),
        )
        current = result[-1]

        if has_inclusion(current, candidate):
            # Find the previous non-inclusive bar for direction.
            prev = result[-2] if len(result) >= 2 else None
            direction = get_merge_direction(current, prev)
            merged = merge_two(current, candidate, direction)
            result[-1] = merged
        else:
            result.append(candidate)

    return result
