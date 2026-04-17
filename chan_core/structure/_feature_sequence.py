"""Feature sequence primitives for segment identification.

See `structure/README.md` S04–S06 for the full specification.
Book references: §6.2–§6.3 from Chan Theory.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from chan_core.common.math_utils import overlap
from chan_core.common.types import Direction
from chan_core.structure._pen import Pen


# ═══════════════════════════════════════════════════════════
#  Types
# ═══════════════════════════════════════════════════════════


class EndType(Enum):
    """Segment termination kind."""

    TYPE1 = "TYPE1"          # §6.3.2 case 1: no gap at (C'_{j-1}, C'_j)
    TYPE2 = "TYPE2"          # §6.3.2 case 2: gap + reverse sequence verified
    EXTENDED = "EXTENDED"    # §6.3.3: segment absorbs subsequent reverse segment
    EXTREME = "EXTREME"      # §6.3.4 case 1: extreme-price fallback
    TENTATIVE = "TENTATIVE"  # §6.1.1: constructive tail, state=BUILDING


@dataclass(frozen=True)
class FeatureElement:
    """Price interval + originating pens."""

    high: float
    low: float
    src_pens: tuple[Pen, ...]


@dataclass(frozen=True)
class SegmentEndResult:
    """Result emitted when Type1End or Type2End commits."""

    j: int
    end_price: float
    end_type: EndType
    end_feature_element: FeatureElement


# ═══════════════════════════════════════════════════════════
#  Primitive predicates
# ═══════════════════════════════════════════════════════════


def _has_inclusion(a: FeatureElement, b: FeatureElement) -> bool:
    """§6.2.2 inclusion between two feature elements."""
    return (a.high >= b.high and a.low <= b.low) or (
        b.high >= a.high and b.low <= a.low
    )


def _merge_star(
    a: FeatureElement, b: FeatureElement, d: Direction
) -> FeatureElement:
    """§6.2.3 directional merge: UP takes (max_h, max_l), DOWN takes (min_h, min_l)."""
    if d == Direction.UP:
        new_high = max(a.high, b.high)
        new_low = max(a.low, b.low)
    else:
        new_high = min(a.high, b.high)
        new_low = min(a.low, b.low)
    return FeatureElement(
        high=new_high,
        low=new_low,
        src_pens=a.src_pens + b.src_pens,
    )


def _gap(a: FeatureElement, b: FeatureElement) -> bool:
    """§6.2.1 gap: adjacent elements have no price overlap."""
    return not overlap(a.low, a.high, b.low, b.high)


def _top_fseq(C: list[FeatureElement], j: int) -> bool:
    """Top fractal on feature sequence (strict four-way inequality)."""
    if j < 1 or j >= len(C) - 1:
        return False
    left, mid, right = C[j - 1], C[j], C[j + 1]
    return (
        mid.high > left.high
        and mid.high > right.high
        and mid.low > left.low
        and mid.low > right.low
    )


def _bot_fseq(C: list[FeatureElement], j: int) -> bool:
    """Bottom fractal on feature sequence (strict four-way inequality)."""
    if j < 1 or j >= len(C) - 1:
        return False
    left, mid, right = C[j - 1], C[j], C[j + 1]
    return (
        mid.low < left.low
        and mid.low < right.low
        and mid.high < left.high
        and mid.high < right.high
    )


# ═══════════════════════════════════════════════════════════
#  Reverse verification sequence (§6.3.2 case 2)
# ═══════════════════════════════════════════════════════════


def _std_verify(
    F_suffix: list[FeatureElement], d_rev: Direction
) -> list[FeatureElement]:
    """Standardise the verification sequence V.

    Unlike the primary C', the first two elements DO process inclusion
    (book §6.3.2 case 2). Merge direction is reverse of segment direction.
    """
    n = len(F_suffix)
    if n == 0:
        return []
    if n == 1:
        return [F_suffix[0]]

    result: list[FeatureElement] = [F_suffix[0]]
    for i in range(1, n):
        f = F_suffix[i]
        if _has_inclusion(result[-1], f):
            result[-1] = _merge_star(result[-1], f, d_rev)
        else:
            result.append(f)
    return result


def _extremum_candidate_set(
    C_j: FeatureElement,
    direction: Direction,
    F: list[FeatureElement],
) -> list[int]:
    """Indices in F whose element achieves C_j's extremum (time-ascending)."""
    if not C_j.src_pens:
        return []

    target = C_j.high if direction == Direction.UP else C_j.low
    src_pen_ids = set(id(p) for p in C_j.src_pens)

    out: list[int] = []
    for t, f in enumerate(F):
        if len(f.src_pens) != 1:
            continue
        p = f.src_pens[0]
        if id(p) not in src_pen_ids:
            continue
        val = f.high if direction == Direction.UP else f.low
        if val == target:
            out.append(t)
    return out


def _reverse_verify(
    C_j: FeatureElement,
    F: list[FeatureElement],
    direction: Direction,
) -> bool:
    """§6.3.2 case 2: verify reverse fractal exists in standardised V."""
    E_j = _extremum_candidate_set(C_j, direction, F)
    if not E_j:
        return False
    t = min(E_j)

    V = F[t:]
    d_rev = Direction.DOWN if direction == Direction.UP else Direction.UP
    V_std = _std_verify(V, d_rev)
    if len(V_std) < 3:
        return False

    verify_fn = _bot_fseq if direction == Direction.UP else _top_fseq
    for r in range(1, len(V_std) - 1):
        if verify_fn(V_std, r):
            return True
    return False


# ═══════════════════════════════════════════════════════════
#  EigenFX: incremental state machine
# ═══════════════════════════════════════════════════════════


class EigenFX:
    """Incremental feature sequence state machine.

    Usage:
        efx = EigenFX(direction=Direction.UP)
        for pen in pens:
            result = efx.add(pen)
            if result is not None:
                break  # segment terminated

    O(1) amortised per add, based on stack invariants of C' and V'
    (non-top positions are immutable once appended).
    """

    def __init__(self, direction: Direction) -> None:
        self.direction = direction
        self._d_rev = (
            Direction.DOWN if direction == Direction.UP else Direction.UP
        )
        self.C: list[FeatureElement] = []
        self.F: list[FeatureElement] = []

        # Pending state: at most one active, locked on earliest j with gap
        self._pending_j: int | None = None
        self._pending_mid: FeatureElement | None = None
        self._pending_end_price: float | None = None
        self._pending_V_std: list[FeatureElement] = []
        self._pending_V_start_t_in_F: int = -1
        self._pending_V_last_checked_r: int = 0

    def add(self, pen: Pen) -> SegmentEndResult | None:
        """Feed one pen; return a result if the segment terminates."""
        if pen.direction == self.direction:
            return None  # same-direction pens do not enter F

        f = FeatureElement(high=pen.high, low=pen.low, src_pens=(pen,))
        self.F.append(f)
        new_f_idx_in_F = len(self.F) - 1

        c_was_appended = self._push_with_inclusion_C(f)

        # With active pending: only extend V and re-check the new r position.
        if self._pending_j is not None:
            if new_f_idx_in_F >= self._pending_V_start_t_in_F:
                v_appended = self._push_V_std_with_inclusion(f)
                if v_appended:
                    result = self._check_new_bot_fractal_on_append()
                    if result is not None:
                        return result
            return None

        # No pending: a new stable j can only emerge when C appends.
        if not c_was_appended:
            return None
        if len(self.C) < 3:
            return None

        j = len(self.C) - 2
        main_fn = _top_fseq if self.direction == Direction.UP else _bot_fseq
        if not main_fn(self.C, j):
            return None

        left = self.C[j - 1]
        mid = self.C[j]
        end_price = mid.high if self.direction == Direction.UP else mid.low

        if not _gap(left, mid):
            # §6.3.2 case 1: Type1End, commit immediately.
            return SegmentEndResult(
                j=j,
                end_price=end_price,
                end_type=EndType.TYPE1,
                end_feature_element=mid,
            )

        # §6.3.2 case 2: enter pending for Type2End verification.
        E_j = _extremum_candidate_set(mid, self.direction, self.F)
        if not E_j:
            return None
        t = min(E_j)

        self._pending_j = j
        self._pending_mid = mid
        self._pending_end_price = end_price
        self._pending_V_start_t_in_F = t
        self._pending_V_std = []
        self._pending_V_last_checked_r = 0

        # Seed V with existing suffix F[t:]; subsequent adds extend O(1).
        for i in range(t, len(self.F)):
            v_appended = self._push_V_std_with_inclusion(self.F[i])
            if v_appended:
                result = self._check_new_bot_fractal_on_append()
                if result is not None:
                    return result

        return None

    def _push_with_inclusion_C(self, f: FeatureElement) -> bool:
        """Stack-push C; first two do not process inclusion (§6.2.3)."""
        if len(self.C) < 2:
            self.C.append(f)
            return True
        top = self.C[-1]
        if _has_inclusion(top, f):
            self.C[-1] = _merge_star(top, f, self.direction)
            return False
        self.C.append(f)
        return True

    def _push_V_std_with_inclusion(self, f: FeatureElement) -> bool:
        """Stack-push V; first two DO process inclusion (§6.3.2 case 2)."""
        if not self._pending_V_std:
            self._pending_V_std.append(f)
            return True
        top = self._pending_V_std[-1]
        if _has_inclusion(top, f):
            self._pending_V_std[-1] = _merge_star(top, f, self._d_rev)
            return False
        self._pending_V_std.append(f)
        return True

    def _check_new_bot_fractal_on_append(self) -> SegmentEndResult | None:
        """Check only the newly-stable r = len(V) - 2."""
        V = self._pending_V_std
        if len(V) < 3:
            return None
        r = len(V) - 2
        if r <= self._pending_V_last_checked_r:
            return None
        self._pending_V_last_checked_r = r
        verify_fn = (
            _bot_fseq if self.direction == Direction.UP else _top_fseq
        )
        if verify_fn(V, r):
            return SegmentEndResult(
                j=self._pending_j,  # type: ignore[arg-type]
                end_price=self._pending_end_price,  # type: ignore[arg-type]
                end_type=EndType.TYPE2,
                end_feature_element=self._pending_mid,  # type: ignore[arg-type]
            )
        return None


# ═══════════════════════════════════════════════════════════
#  End-pen index mapping
# ═══════════════════════════════════════════════════════════


def map_end_pen_idx(
    all_pens: list[Pen],
    seg_first_pen_idx: int,
    result: SegmentEndResult,
    direction: Direction,
    F: list[FeatureElement],
) -> int | None:
    """Map the triggering feature element back to the segment's last pen.

    The last pen is the same-direction pen immediately before the pen that
    reaches C'_j's extremum. Returns None if the resulting segment length
    violates A1 (odd, ≥ 3).
    """
    E_j = _extremum_candidate_set(result.end_feature_element, direction, F)
    if not E_j:
        return None
    t = min(E_j)
    target_pen = F[t].src_pens[0]

    abs_p: int | None = None
    for idx in range(seg_first_pen_idx + 1, len(all_pens)):
        if all_pens[idx] is target_pen:
            abs_p = idx
            break
    if abs_p is None:
        return None

    end_idx = abs_p - 1
    seg_len = end_idx - seg_first_pen_idx + 1
    if seg_len < 3 or seg_len % 2 != 1:
        return None
    return end_idx


__all__ = [
    "EndType",
    "FeatureElement",
    "SegmentEndResult",
    "EigenFX",
    "map_end_pen_idx",
    # Exposed helpers (consumed by tests and _segment.py).
    "_has_inclusion",
    "_merge_star",
    "_gap",
    "_top_fseq",
    "_bot_fseq",
    "_std_verify",
    "_extremum_candidate_set",
    "_reverse_verify",
]
