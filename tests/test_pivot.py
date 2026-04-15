"""Task 09-10 tests: pivot formation, extension, leave, search."""

import csv
import os

import pytest

from chan_core.common.kline import MergedKLine, RawKLine
from chan_core.common.types import Direction, FractalType
from chan_core.engine import PivotSnapshot
from chan_core.structure._fractal import Fractal, find_fractals
from chan_core.structure._merge import merge_inclusive
from chan_core.structure._pen import Pen, build_confirmed, build_pens
from chan_core.structure._pivot import (
    PivotBuilder,
    apply_extension,
    check_extension,
    check_leave,
    search_pivots,
    try_form_pivot,
)


# ── Helpers ───────────────────────────────────────────────


def _mk(high: float, low: float, idx: int) -> MergedKLine:
    return MergedKLine(high=high, low=low, timestamp=f"t{idx:04d}", source_indices=(idx,))


def _fractal(ft: FractalType, val: float, idx: int) -> Fractal:
    if ft == FractalType.TOP:
        left = _mk(val - 2, val - 4, idx - 1)
        mid = _mk(val, val - 2, idx)
        right = _mk(val - 2, val - 4, idx + 1)
    else:
        left = _mk(val + 4, val + 2, idx - 1)
        mid = _mk(val + 2, val, idx)
        right = _mk(val + 4, val + 2, idx + 1)
    return Fractal(type=ft, value=val, klines=(left, mid, right), index=idx)


def _pen(start_val: float, end_val: float, start_idx: int, end_idx: int,
         direction: Direction) -> Pen:
    if direction == Direction.UP:
        start_f = _fractal(FractalType.BOT, start_val, start_idx)
        end_f = _fractal(FractalType.TOP, end_val, end_idx)
    else:
        start_f = _fractal(FractalType.TOP, start_val, start_idx)
        end_f = _fractal(FractalType.BOT, end_val, end_idx)
    return Pen(start=start_f, end=end_f, direction=direction)


# ═══════════════════════════════════════════════════════════
#  try_form_pivot
# ═══════════════════════════════════════════════════════════


def test_pivot_forms_with_strict_overlap() -> None:
    """Three pens with strict overlap → pivot forms."""
    p1 = _pen(10, 20, 1, 10, Direction.UP)    # [10, 20]
    p2 = _pen(18, 12, 10, 20, Direction.DOWN)  # [12, 18]
    p3 = _pen(11, 19, 20, 30, Direction.UP)    # [11, 19]
    pivot = try_form_pivot(p1, p2, p3)
    assert pivot is not None
    assert pivot.zg == 18  # min(20, 18, 19)
    assert pivot.zd == 12  # max(10, 12, 11)
    assert pivot.gg == 20  # max(20, 18, 19)
    assert pivot.dd == 10  # min(10, 12, 11)


def test_pivot_fails_zd_equals_zg() -> None:
    """ZD == ZG → strict inequality fails → no pivot."""
    p1 = _pen(10, 15, 1, 10, Direction.UP)    # [10, 15]
    p2 = _pen(15, 10, 10, 20, Direction.DOWN)  # [10, 15]
    p3 = _pen(10, 15, 20, 30, Direction.UP)    # [10, 15]
    # ZG=min(15,15,15)=15, ZD=max(10,10,10)=10, ZD<ZG → forms!
    # Actually this forms. Let me make one where ZD==ZG
    p1 = _pen(5, 15, 1, 10, Direction.UP)     # [5, 15]
    p2 = _pen(20, 10, 10, 20, Direction.DOWN)  # [10, 20]
    p3 = _pen(8, 15, 20, 30, Direction.UP)     # [8, 15]
    # ZG=min(15,20,15)=15, ZD=max(5,10,8)=10, ZD<ZG → forms!
    # Need: ZD==ZG
    p1b = _pen(5, 10, 1, 10, Direction.UP)     # [5, 10]
    p2b = _pen(15, 10, 10, 20, Direction.DOWN)  # [10, 15]
    p3b = _pen(5, 10, 20, 30, Direction.UP)     # [5, 10]
    # ZG=min(10,15,10)=10, ZD=max(5,10,5)=10 → ZD==ZG → fails
    assert try_form_pivot(p1b, p2b, p3b) is None


def test_pivot_fails_no_overlap() -> None:
    """Disjoint intervals → ZD > ZG → no pivot."""
    p1 = _pen(10, 15, 1, 10, Direction.UP)    # [10, 15]
    p2 = _pen(20, 18, 10, 20, Direction.DOWN)  # [18, 20]
    p3 = _pen(5, 8, 20, 30, Direction.UP)      # [5, 8]
    # ZG=min(15,20,8)=8, ZD=max(10,18,5)=18 → ZD>ZG → fails
    assert try_form_pivot(p1, p2, p3) is None


def test_pivot_four_boundary_invariant() -> None:
    """DD ≤ ZD < ZG ≤ GG."""
    p1 = _pen(10, 20, 1, 10, Direction.UP)
    p2 = _pen(18, 12, 10, 20, Direction.DOWN)
    p3 = _pen(11, 19, 20, 30, Direction.UP)
    pivot = try_form_pivot(p1, p2, p3)
    assert pivot is not None
    assert pivot.dd <= pivot.zd < pivot.zg <= pivot.gg


def test_pivot_same_interval_forms() -> None:
    """Three pens with identical intervals → forms (ZD<ZG)."""
    p1 = _pen(10, 20, 1, 10, Direction.UP)
    p2 = _pen(20, 10, 10, 20, Direction.DOWN)
    p3 = _pen(10, 20, 20, 30, Direction.UP)
    pivot = try_form_pivot(p1, p2, p3)
    assert pivot is not None


# ═══════════════════════════════════════════════════════════
#  Extension / Leave
# ═══════════════════════════════════════════════════════════


def _make_pivot() -> PivotBuilder:
    p1 = _pen(10, 20, 1, 10, Direction.UP)
    p2 = _pen(18, 12, 10, 20, Direction.DOWN)
    p3 = _pen(11, 19, 20, 30, Direction.UP)
    pivot = try_form_pivot(p1, p2, p3)
    assert pivot is not None
    return pivot


def test_extension_overlaps() -> None:
    pivot = _make_pivot()  # ZD=12, ZG=18
    p = _pen(15, 17, 30, 40, Direction.DOWN)  # [15,17] overlaps [12,18]
    assert check_extension(p, pivot) is True


def test_extension_endpoint_touches_zg() -> None:
    """Pen high == ZG → closed interval overlap."""
    pivot = _make_pivot()  # ZD=12, ZG=18
    p = _pen(5, 12, 30, 40, Direction.UP)  # [5,12] touches ZD=12
    assert check_extension(p, pivot) is True


def test_extension_endpoint_touches_zd() -> None:
    pivot = _make_pivot()  # ZD=12, ZG=18
    p = _pen(18, 25, 30, 40, Direction.UP)  # [18,25] touches ZG=18
    assert check_extension(p, pivot) is True


def test_leave_up() -> None:
    pivot = _make_pivot()  # ZD=12, ZG=18
    p = _pen(19, 25, 30, 40, Direction.UP)  # [19,25] > ZG=18
    result = check_leave(p, pivot)
    assert result == Direction.UP


def test_leave_down() -> None:
    pivot = _make_pivot()  # ZD=12, ZG=18
    p = _pen(11, 5, 30, 40, Direction.DOWN)  # [5,11] < ZD=12
    result = check_leave(p, pivot)
    assert result == Direction.DOWN


def test_extension_preserves_zd_zg() -> None:
    pivot = _make_pivot()
    old_zd, old_zg = pivot.zd, pivot.zg
    p = _pen(8, 22, 30, 40, Direction.UP)  # [8,22] overlaps, extends range
    apply_extension(p, pivot)
    assert pivot.zd == old_zd
    assert pivot.zg == old_zg
    assert pivot.gg == 22  # updated
    assert pivot.dd == 8   # updated


def test_extension_updates_gg_dd() -> None:
    pivot = _make_pivot()  # GG=20, DD=10
    p = _pen(5, 25, 30, 40, Direction.UP)  # [5,25]
    apply_extension(p, pivot)
    assert pivot.gg == 25
    assert pivot.dd == 5


def test_dd_le_zd_lt_zg_le_gg_after_extension() -> None:
    """DD ≤ ZD < ZG ≤ GG holds after extension."""
    pivot = _make_pivot()
    for i in range(20):
        p = _pen(float(5 + i), float(22 + i), 30 + i * 10, 40 + i * 10, Direction.UP)
        if check_extension(p, pivot):
            apply_extension(p, pivot)
    assert pivot.dd <= pivot.zd < pivot.zg <= pivot.gg


# ═══════════════════════════════════════════════════════════
#  search_pivots
# ═══════════════════════════════════════════════════════════


def test_search_pivots_basic() -> None:
    """Simple 3-pen pivot → 1 pivot found."""
    pens: list[Pen] = [
        _pen(10, 20, 1, 10, Direction.UP),
        _pen(18, 12, 10, 20, Direction.DOWN),
        _pen(11, 19, 20, 30, Direction.UP),
    ]
    pivots = search_pivots(pens)
    assert len(pivots) == 1


def test_search_pivots_with_leave_and_new() -> None:
    """Pivot, then leave, then new pivot."""
    pens: list[Pen] = [
        _pen(10, 20, 1, 10, Direction.UP),      # P0
        _pen(18, 12, 10, 20, Direction.DOWN),    # P1
        _pen(11, 19, 20, 30, Direction.UP),      # P2
        # P0-P2 form Z0, ZD=12, ZG=18
        _pen(19, 25, 30, 40, Direction.DOWN),    # P3 leaves up (low=19>ZG=18)
        # leave_pen = P3, new search from P4 (leave+1)
        _pen(25, 35, 40, 50, Direction.UP),      # P4
        _pen(33, 28, 50, 60, Direction.DOWN),    # P5
        _pen(27, 34, 60, 70, Direction.UP),      # P6
        # P4-P6 form Z1
    ]
    pivots = search_pivots(pens)
    assert len(pivots) == 2
    assert pivots[0].zd == 12
    assert pivots[0].zg == 18
    assert pivots[1].zd == max(25, 28, 27)  # 28
    assert pivots[1].zg == min(35, 33, 34)  # 33


def test_search_pivots_leave_plus_1() -> None:
    """Leave pen is NOT part of new pivot search (S09)."""
    pens: list[Pen] = [
        _pen(10, 20, 1, 10, Direction.UP),
        _pen(18, 12, 10, 20, Direction.DOWN),
        _pen(11, 19, 20, 30, Direction.UP),
        _pen(19, 25, 30, 40, Direction.DOWN),  # leave pen
        _pen(25, 35, 40, 50, Direction.UP),    # search starts here
        _pen(33, 28, 50, 60, Direction.DOWN),
        _pen(27, 34, 60, 70, Direction.UP),
    ]
    pivots = search_pivots(pens)
    # Leave pen (P3) should NOT be in Z1's components
    assert len(pivots) == 2
    z1_components = pivots[1].components
    leave_pen = pens[3]
    assert leave_pen not in z1_components


def test_search_pivots_empty() -> None:
    assert search_pivots([]) == []


def test_search_pivots_less_than_3() -> None:
    pens: list[Pen] = [_pen(10, 20, 1, 10, Direction.UP)]
    assert search_pivots(pens) == []


def test_search_pivots_no_overlap() -> None:
    """Three pens with no overlap → no pivot."""
    pens: list[Pen] = [
        _pen(1, 5, 1, 10, Direction.UP),
        _pen(10, 8, 10, 20, Direction.DOWN),
        _pen(15, 20, 20, 30, Direction.UP),
    ]
    assert search_pivots(pens) == []


def test_search_continuous_extension() -> None:
    """20+ pens all extending → 1 pivot with many components."""
    pens: list[Pen] = []
    for i in range(21):
        if i % 2 == 0:
            pens.append(_pen(10.0, 20.0, i * 10, i * 10 + 5, Direction.UP))
        else:
            pens.append(_pen(18.0, 12.0, i * 10, i * 10 + 5, Direction.DOWN))
    pivots = search_pivots(pens)
    assert len(pivots) == 1
    assert len(pivots[0].components) == 21


def test_snapshot_frozen() -> None:
    p1 = _pen(10, 20, 1, 10, Direction.UP)
    p2 = _pen(18, 12, 10, 20, Direction.DOWN)
    p3 = _pen(11, 19, 20, 30, Direction.UP)
    pivot = try_form_pivot(p1, p2, p3)
    assert pivot is not None
    snap = pivot.to_snapshot()
    assert isinstance(snap, PivotSnapshot)
    with pytest.raises(AttributeError):
        snap.zd = 999.0  # type: ignore[misc]


# ═══════════════════════════════════════════════════════════
#  Fixed sample: 300811.SZ pivots
# ═══════════════════════════════════════════════════════════


def _load_300811_pens() -> list[Pen]:
    csv_path = os.path.join(
        os.path.dirname(__file__),
        "..",
        "doc",
        "cache",
        "300811.SZ_20250411_20260410.csv",
    )
    raw: list[RawKLine] = []
    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            raw.append(
                RawKLine(
                    high=float(row["high"]),
                    low=float(row["low"]),
                    timestamp=row["trade_date"],
                )
            )
    merged = merge_inclusive(raw)
    fractals = find_fractals(merged)
    confirmed = build_confirmed(fractals)
    return build_pens(confirmed)


def test_300811_pivot_count() -> None:
    """300811.SZ: 17 pens → 2 pivots."""
    pens = _load_300811_pens()
    pivots = search_pivots(pens)
    assert len(pivots) == 2


def test_300811_z0_boundaries() -> None:
    """Z0: initial P0,P1,P2 → ZD=40.51, ZG=44.07."""
    pens = _load_300811_pens()
    pivots = search_pivots(pens)
    z0 = pivots[0]
    assert z0.zg == pytest.approx(44.07, abs=0.01)
    assert z0.zd == pytest.approx(40.51, abs=0.01)


def test_300811_z0_extension_then_leave() -> None:
    """Z0: P3 extends, P4 leaves upward."""
    pens = _load_300811_pens()
    pivots = search_pivots(pens)
    z0 = pivots[0]
    # P3 extends (UP 40.51→62.53 overlaps [40.51, 44.07])
    assert len(z0.components) == 4  # P0,P1,P2,P3


def test_300811_z1_starts_from_p5() -> None:
    """Z1 search starts from P5 (leave_pen P4 + 1)."""
    pens = _load_300811_pens()
    pivots = search_pivots(pens)
    z1 = pivots[1]
    # P5 = UP from 54.40 to 82.50
    assert z1.zg == pytest.approx(82.50, abs=0.01)
    assert z1.zd == pytest.approx(68.59, abs=0.01)


def test_300811_z1_no_leave() -> None:
    """Z1: all remaining pens extend, no leave."""
    pens = _load_300811_pens()
    pivots = search_pivots(pens)
    z1 = pivots[1]
    # P5 through P16 should all extend (12 components)
    expected_components = len(pens) - 5  # P5..P16 = 12
    assert len(z1.components) == expected_components


def test_300811_four_boundary_invariant() -> None:
    """DD ≤ ZD < ZG ≤ GG for all pivots."""
    pens = _load_300811_pens()
    pivots = search_pivots(pens)
    for p in pivots:
        assert p.dd <= p.zd < p.zg <= p.gg
