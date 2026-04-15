"""Fake data to verify C2 under different fractal inclusion conditions.

Three datasets:
  A: No inclusion — each standard K-line = 1 raw K-line
  B: Inclusion in between — merged gap small but raw gap large
  C: Inclusion inside fractal — fractal's standard K-line contains many raw bars
"""

from chan_core.common.kline import RawKLine, MergedKLine
from chan_core.common.types import Direction, FractalType
from chan_core.structure._merge import merge_inclusive, has_inclusion
from chan_core.structure._fractal import find_fractals


# ═══════════════════════════════════════════════════════════
#  Dataset A: No inclusion at all
#
#  8 raw K-lines, no inclusion → 8 standard K-lines
#  Bot fractal at merged[1], Top fractal at merged[6]
#  merged gap = 5, raw gap between extremes = 4
#
#  idx:  0       1       2       3       4       5       6       7
#  h:   10       7       9      11      13      12      15      13
#  l:    8       5       6       7       9      10      12      11
# ═══════════════════════════════════════════════════════════

DATASET_A = [
    RawKLine(high=10, low=8, timestamp="A0"),   # m0
    RawKLine(high=7, low=5, timestamp="A1"),    # m1 ← bot extreme
    RawKLine(high=9, low=6, timestamp="A2"),    # m2
    RawKLine(high=11, low=7, timestamp="A3"),   # m3
    RawKLine(high=14, low=10, timestamp="A4"),  # m4
    RawKLine(high=16, low=11, timestamp="A5"),  # m5
    RawKLine(high=20, low=15, timestamp="A6"),  # m6 ← top extreme
    RawKLine(high=18, low=13, timestamp="A7"),  # m7
]


def test_dataset_a_merge() -> None:
    merged = merge_inclusive(DATASET_A)
    assert len(merged) == 8, f"Expected 8 (no inclusion), got {len(merged)}"
    for i in range(len(merged) - 1):
        assert not has_inclusion(merged[i], merged[i + 1])


def test_dataset_a_fractals() -> None:
    merged = merge_inclusive(DATASET_A)
    fractals = find_fractals(merged)
    bots = [f for f in fractals if f.type == FractalType.BOT]
    tops = [f for f in fractals if f.type == FractalType.TOP]
    assert any(f.index == 1 and f.value == 5 for f in bots), f"No BOT at idx=1, got {bots}"
    assert any(f.index == 6 and f.value == 20 for f in tops), f"No TOP at idx=6, got {tops}"


def test_dataset_a_c2_analysis() -> None:
    """No inclusion: merged gap=5, raw gap=4. All C2 interpretations pass."""
    merged = merge_inclusive(DATASET_A)
    fractals = find_fractals(merged)
    bot = next(f for f in fractals if f.index == 1)
    top = next(f for f in fractals if f.index == 6)

    merged_gap = abs(top.index - bot.index)
    raw_between = min(top.klines[1].source_indices) - max(bot.klines[1].source_indices) - 1
    total_raw = max(top.klines[2].source_indices) - min(bot.klines[0].source_indices) + 1

    print(f"\n[Dataset A] No inclusion:")
    print(f"  merged gap = {merged_gap}")
    print(f"  raw between extremes = {raw_between}")
    print(f"  total raw in pen = {total_raw}")
    print(f"  C2 (merged gap>=5): {merged_gap >= 5}")
    print(f"  C2 (raw between>=3): {raw_between >= 3}")
    print(f"  C2 (total raw>=5): {total_raw >= 5}")

    assert merged_gap == 5
    assert raw_between == 4
    assert total_raw == 8


# ═══════════════════════════════════════════════════════════
#  Dataset B: Inclusion BETWEEN fractals
#
#  8 raw K-lines, raw[2,3,4] merge into 1 standard K-line
#  → 6 standard K-lines total
#  Bot fractal at merged[1], Top fractal at merged[4]
#  merged gap = 3, but raw gap between extremes = 4
#
#  raw:  K0      K1      K2      K3      K4      K5      K6      K7
#  h:    10       7      12      11      10      14      17      15
#  l:     8       5       6       7       8      10      13      12
#
#  merged: m0(10,8) m1(7,5) m2(12,8)[K2+K3+K4] m3(14,10) m4(17,13) m5(15,12)
#
#  Key: merged gap=3, old C2 rejects. raw gap=4, new C2 accepts.
# ═══════════════════════════════════════════════════════════

DATASET_B = [
    RawKLine(high=10, low=8, timestamp="B0"),
    RawKLine(high=7, low=5, timestamp="B1"),
    RawKLine(high=12, low=6, timestamp="B2"),   # inclusion chain start
    RawKLine(high=11, low=7, timestamp="B3"),   # included in B2
    RawKLine(high=10, low=8, timestamp="B4"),   # included in B2+B3
    RawKLine(high=14, low=10, timestamp="B5"),
    RawKLine(high=17, low=13, timestamp="B6"),
    RawKLine(high=15, low=12, timestamp="B7"),
]


def test_dataset_b_merge() -> None:
    merged = merge_inclusive(DATASET_B)
    assert len(merged) == 6, f"Expected 6 (3 bars merged), got {len(merged)}"
    # m2 should contain raw indices [2, 3, 4]
    assert merged[2].source_indices == (2, 3, 4), f"Got {merged[2].source_indices}"
    for i in range(len(merged) - 1):
        assert not has_inclusion(merged[i], merged[i + 1])


def test_dataset_b_fractals() -> None:
    merged = merge_inclusive(DATASET_B)
    fractals = find_fractals(merged)
    bots = [f for f in fractals if f.type == FractalType.BOT]
    tops = [f for f in fractals if f.type == FractalType.TOP]
    assert any(f.index == 1 and f.value == 5 for f in bots), f"Got {bots}"
    assert any(f.index == 4 and f.value == 17 for f in tops), f"Got {tops}"


def test_dataset_b_c2_analysis() -> None:
    """Inclusion between fractals: merged gap=3 (old rejects), raw gap=4 (new accepts)."""
    merged = merge_inclusive(DATASET_B)
    fractals = find_fractals(merged)
    bot = next(f for f in fractals if f.index == 1)
    top = next(f for f in fractals if f.index == 4)

    merged_gap = abs(top.index - bot.index)
    raw_between = min(top.klines[1].source_indices) - max(bot.klines[1].source_indices) - 1
    total_raw = max(top.klines[2].source_indices) - min(bot.klines[0].source_indices) + 1

    print(f"\n[Dataset B] Inclusion between fractals:")
    print(f"  merged[2] source = {merged[2].source_indices}")
    print(f"  merged gap = {merged_gap}")
    print(f"  raw between extremes = {raw_between}")
    print(f"  total raw in pen = {total_raw}")
    print(f"  C2 (merged gap>=5): {merged_gap >= 5}  ← OLD: wrongly rejects")
    print(f"  C2 (raw between>=3): {raw_between >= 3}  ← NEW: correctly accepts")
    print(f"  C2 (total raw>=5): {total_raw >= 5}")

    assert merged_gap == 3
    assert raw_between == 4   # K2,K3,K4,K5 between K1 and K6
    assert total_raw == 8


# ═══════════════════════════════════════════════════════════
#  Dataset C: Inclusion INSIDE fractal
#
#  Bot fractal's middle standard K-line merges from 5 raw K-lines
#  → Bot fractal alone has 7 raw K-lines
#  Top fractal at merged gap=3, only 2 standard bars between
#  But raw gap between extremes is still large
#
#  raw:  K0     K1    K2    K3    K4    K5    K6     K7     K8      K9
#  h:    10      8     7     6     5     9    11     14     17      15
#  l:     6      4     3     2     1     5     7     10     13      12
#
#  merged: m0(10,6) m1(8,1)[K1-K5] m2(9,5) m3(11,7) m4(14,10) m5(17,13) m6(15,12)
# ═══════════════════════════════════════════════════════════

DATASET_C = [
    RawKLine(high=15, low=10, timestamp="C0"),
    RawKLine(high=12, low=5, timestamp="C1"),   # inclusion chain start
    RawKLine(high=11, low=6, timestamp="C2"),   # included
    RawKLine(high=10, low=7, timestamp="C3"),   # included
    RawKLine(high=9, low=6, timestamp="C4"),    # included
    RawKLine(high=8, low=7, timestamp="C5"),    # included
    RawKLine(high=13, low=9, timestamp="C6"),
    RawKLine(high=11, low=7, timestamp="C7"),
    RawKLine(high=17, low=13, timestamp="C8"),
    RawKLine(high=15, low=12, timestamp="C9"),
]


def test_dataset_c_merge() -> None:
    merged = merge_inclusive(DATASET_C)
    print(f"\n[Dataset C] Merged result:")
    for i, m in enumerate(merged):
        print(f"  m{i}: h={m.high} l={m.low} src={m.source_indices}")
    # m1 should absorb raw [1,2,3,4,5]
    assert len(merged) == 6, f"Expected 6, got {len(merged)}"
    assert len(merged[1].source_indices) == 5, (
        f"Expected m1 to absorb 5 raw bars, got {merged[1].source_indices}"
    )


def test_dataset_c_fractals() -> None:
    merged = merge_inclusive(DATASET_C)
    fractals = find_fractals(merged)
    print(f"\n[Dataset C] Fractals:")
    for f in fractals:
        print(f"  {f.type.name} val={f.value} idx={f.index} mid_src={f.klines[1].source_indices}")
    bots = [f for f in fractals if f.type == FractalType.BOT]
    tops = [f for f in fractals if f.type == FractalType.TOP]
    assert any(f.index == 1 for f in bots)
    assert any(f.index == 4 for f in tops)


def test_dataset_c_c2_analysis() -> None:
    """Inclusion INSIDE fractal: merged gap=3, raw between=2, total raw=10.

    This is the critical case the user identified:
    - Bot fractal's middle bar absorbed 5 raw K-lines
    - merged gap and raw-between both fail
    - But total raw in pen = 10, clearly a valid pen
    """
    merged = merge_inclusive(DATASET_C)
    fractals = find_fractals(merged)
    bot = next(f for f in fractals if f.index == 1)
    top = next(f for f in fractals if f.index == 4)

    merged_gap = abs(top.index - bot.index)
    raw_between = min(top.klines[1].source_indices) - max(bot.klines[1].source_indices) - 1
    total_raw = max(top.klines[2].source_indices) - min(bot.klines[0].source_indices) + 1

    print(f"\n[Dataset C] Inclusion INSIDE fractal:")
    print(f"  Bot mid source = {bot.klines[1].source_indices} (5 raw bars)")
    print(f"  Top mid source = {top.klines[1].source_indices}")
    print(f"  merged gap = {merged_gap}")
    print(f"  raw between extremes = {raw_between}")
    print(f"  total raw in pen = {total_raw}")
    print(f"  C2 (merged gap>=5): {merged_gap >= 5}  ← WRONG: rejects")
    print(f"  C2 (raw between>=3): {raw_between >= 3}  ← WRONG: rejects")
    print(f"  C2 (total raw>=5): {total_raw >= 5}  ← CORRECT: accepts")

    assert merged_gap == 3
    assert raw_between == 2
    assert total_raw == 10


# ═══════════════════════════════════════════════════════════
#  Summary comparison
# ═══════════════════════════════════════════════════════════

def test_summary_all_datasets() -> None:
    """Print comparison table of all three C2 interpretations."""
    datasets: list[tuple[str, list[RawKLine]]] = [
        ("A: No inclusion", DATASET_A),
        ("B: Inclusion between", DATASET_B),
        ("C: Inclusion inside fractal", DATASET_C),
    ]

    print("\n" + "=" * 80)
    print("C2 interpretation comparison")
    print("=" * 80)
    print(f"{'Dataset':<30} {'merged_gap':>10} {'raw_between':>12} {'total_raw':>10} | {'gap>=5':>7} {'btw>=3':>7} {'tot>=5':>7}")
    print("-" * 80)

    for name, raw_data in datasets:
        merged = merge_inclusive(raw_data)
        fractals = find_fractals(merged)
        bots = [f for f in fractals if f.type == FractalType.BOT]
        tops = [f for f in fractals if f.type == FractalType.TOP]
        if not bots or not tops:
            continue
        bot = bots[0]
        top = tops[-1]

        mg = abs(top.index - bot.index)
        rb = min(top.klines[1].source_indices) - max(bot.klines[1].source_indices) - 1
        tr = max(top.klines[2].source_indices) - min(bot.klines[0].source_indices) + 1

        g5 = "✓" if mg >= 5 else "✗"
        b3 = "✓" if rb >= 3 else "✗"
        t5 = "✓" if tr >= 5 else "✗"

        print(f"{name:<30} {mg:>10} {rb:>12} {tr:>10} | {g5:>7} {b3:>7} {t5:>7}")

    print("=" * 80)
    print("Conclusion: only 'total raw >= 5' handles ALL cases correctly")
    print("  - Dataset C proves: inclusion inside fractal defeats both")
    print("    merged-gap and raw-between counting")
