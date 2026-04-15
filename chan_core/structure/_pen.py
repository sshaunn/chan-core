"""Pen (笔) value object and confirmed-list algorithm.

Implements S03: confirmed list algorithm with C1/C2/C4 conditions.
"""

from dataclasses import dataclass

from chan_core.common.types import Direction, FractalType
from chan_core.structure._fractal import Fractal


@dataclass(frozen=True)
class Pen:
    """A single pen connecting two fractals of opposite polarity.

    Fields:
        start:     starting fractal
        end:       ending fractal
        direction: UP (Bot→Top) or DOWN (Top→Bot)
    """

    start: Fractal
    end: Fractal
    direction: Direction

    @property
    def high(self) -> float:
        return max(self.start.value, self.end.value)

    @property
    def low(self) -> float:
        return min(self.start.value, self.end.value)

    @property
    def interval(self) -> tuple[float, float]:
        return (self.low, self.high)


def check_c1(a: Fractal, b: Fractal) -> bool:
    """C1 (fractal independence): KLines(a) ∩ KLines(b) = ∅.

    Two fractals' 3-bar sets are disjoint iff their middle indices
    differ by at least 3.
    """
    return abs(b.index - a.index) >= 3


def check_c2(a: Fractal, b: Fractal) -> bool:
    """C2 (raw K-line gap): at least 2 raw K-lines between two fractal extremes.

    K_p = extreme (middle) merged bar of F_a
    K_q = extreme (middle) merged bar of F_b
    Count raw K-lines strictly between K_p's last raw bar and K_q's first raw bar.
    Require ≥ 2 (equivalently, raw index diff ≥ 3).

    C1 checks structural independence on standard K-lines.
    C2 checks distance on raw K-lines. Both must pass.
    """
    a_last_raw = max(a.klines[1].source_indices)
    b_first_raw = min(b.klines[1].source_indices)
    raw_gap = b_first_raw - a_last_raw  # raw index diff
    return raw_gap >= 3


def check_c4(a: Fractal, b: Fractal) -> bool:
    """C4 (price validity): val(top) > val(bot)."""
    if a.type == FractalType.TOP:
        return a.value > b.value
    else:
        return b.value > a.value


def build_confirmed(fractals: list[Fractal]) -> list[Fractal]:
    """Build the confirmed fractal list using the §6.4 algorithm.

    Same-type: keep more extreme (top→higher, bot→lower).
    Opposite-type: append only if C1 ∧ C2 ∧ C4.
    """
    if not fractals:
        return []

    confirmed: list[Fractal] = [fractals[0]]

    for f in fractals[1:]:
        last = confirmed[-1]

        if f.type == last.type:
            # Same polarity: keep the more extreme value
            if f.type == FractalType.TOP:
                if f.value > last.value:
                    confirmed[-1] = f
            else:
                if f.value < last.value:
                    confirmed[-1] = f
        else:
            # Opposite polarity: check pen conditions
            if check_c1(last, f) and check_c2(last, f) and check_c4(last, f):
                confirmed.append(f)
            # else: skip this fractal

    return confirmed


def build_pens(confirmed: list[Fractal]) -> list[Pen]:
    """Pair consecutive confirmed fractals into pens.

    pen[k].end == confirmed[k+1] == pen[k+1].start (zero-gap).
    """
    pens: list[Pen] = []
    for i in range(len(confirmed) - 1):
        a, b = confirmed[i], confirmed[i + 1]
        if a.type == FractalType.BOT:
            direction = Direction.UP
        else:
            direction = Direction.DOWN
        pens.append(Pen(start=a, end=b, direction=direction))
    return pens
