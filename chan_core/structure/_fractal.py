"""Fractal detection (S02).

See `structure/README.md` S02 for the full specification.
"""

from dataclasses import dataclass

from chan_core.common.kline import MergedKLine
from chan_core.common.types import FractalType


@dataclass(frozen=True)
class Fractal:
    """A top or bottom fractal formed by three consecutive merged K-lines.

    Fields:
        type:   TOP or BOT
        value:  the extreme price (high for TOP, low for BOT)
        klines: the three merged K-lines forming this fractal
        index:  index of the *middle* K-line in the merged sequence
    """

    type: FractalType
    value: float
    klines: tuple[MergedKLine, MergedKLine, MergedKLine]
    index: int


def _is_top(left: MergedKLine, mid: MergedKLine, right: MergedKLine) -> bool:
    """Top fractal: all four strict inequalities on the middle bar."""
    return (
        mid.high > left.high
        and mid.high > right.high
        and mid.low > left.low
        and mid.low > right.low
    )


def _is_bot(left: MergedKLine, mid: MergedKLine, right: MergedKLine) -> bool:
    """Bottom fractal: all four strict inequalities on the middle bar."""
    return (
        mid.low < left.low
        and mid.low < right.low
        and mid.high < left.high
        and mid.high < right.high
    )


def find_fractals(merged_klines: list[MergedKLine]) -> list[Fractal]:
    """Detect all fractals in a merged K-line sequence.

    Sliding window of size 3.  First and last bars cannot be the
    middle element of a fractal.
    """
    result: list[Fractal] = []
    n = len(merged_klines)
    if n < 3:
        return result

    for i in range(1, n - 1):
        left, mid, right = merged_klines[i - 1], merged_klines[i], merged_klines[i + 1]

        if _is_top(left, mid, right):
            result.append(
                Fractal(
                    type=FractalType.TOP,
                    value=mid.high,
                    klines=(left, mid, right),
                    index=i,
                )
            )
        elif _is_bot(left, mid, right):
            result.append(
                Fractal(
                    type=FractalType.BOT,
                    value=mid.low,
                    klines=(left, mid, right),
                    index=i,
                )
            )

    return result
