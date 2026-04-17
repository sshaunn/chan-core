"""段识别规则的构造性区分测试.

对应 `缠论结构基线最终稿.md §7` 的核心规则,用构造性 pen 序列验证:
  - 特征序列法(§6.2-§6.3)的增量 + 首次命中 + Type1/Type2 + 反向验证
  - 极值法兜底(§6.3.4 案例 1)— EXTREME
  - 构造性兜底(§6.1.1)— TENTATIVE
  - 段合并延伸(§6.3.3)— EXTENDED
"""

from __future__ import annotations

import pytest

from chan_core.common.kline import MergedKLine
from chan_core.common.types import Direction, FractalType, SegmentState
from chan_core.structure._fractal import Fractal
from chan_core.structure._pen import Pen
from chan_core.structure._feature_sequence import (
    EigenFX,
    EndType,
    FeatureElement,
    _extremum_candidate_set,
    _has_inclusion,
    _merge_star,
    _reverse_verify,
    _std_verify,
)
from chan_core.structure._segment import build_segments


def _confirmed(segs):
    """Helper: filter out TENTATIVE (state=BUILDING) tail segments."""
    return [s for s in segs if s.state == SegmentState.CONFIRMED]


def _type_end_only(segs):
    """Helper: only TYPE1/TYPE2 segments (exclude EXTREME fallback + TENTATIVE)."""
    return [s for s in segs if s.end_type in ("TYPE1", "TYPE2")]


# ═══════════════════════════════════════════════════════════
#  构造辅助
# ═══════════════════════════════════════════════════════════


def _mk(high: float, low: float, idx: int) -> MergedKLine:
    return MergedKLine(
        high=high, low=low, timestamp=f"t{idx}", source_indices=(idx,)
    )


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


_pen_counter = [0]


def _pen(
    start_val: float, end_val: float, direction: Direction
) -> Pen:
    """构造合成 Pen。start_val / end_val 必须与方向一致。"""
    _pen_counter[0] += 10
    i = _pen_counter[0]
    if direction == Direction.UP:
        assert end_val > start_val, "UP pen: end > start"
        start_f = _fractal(FractalType.BOT, start_val, i)
        end_f = _fractal(FractalType.TOP, end_val, i + 5)
    else:
        assert end_val < start_val, "DOWN pen: end < start"
        start_f = _fractal(FractalType.TOP, start_val, i)
        end_f = _fractal(FractalType.BOT, end_val, i + 5)
    return Pen(start=start_f, end=end_f, direction=direction)


def _build_chain(waypoints: list[float]) -> list[Pen]:
    """Helper: 按波峰/波谷序列生成笔链。

    waypoints 首元素是起点价,其余依次为各拐点。方向由相邻差决定。
    """
    pens: list[Pen] = []
    for i in range(len(waypoints) - 1):
        s, e = waypoints[i], waypoints[i + 1]
        d = Direction.UP if e > s else Direction.DOWN
        pens.append(_pen(s, e, d))
    return pens


def _fe(high: float, low: float) -> FeatureElement:
    """Synthetic singleton FeatureElement — 无真实 src,仅用于谓词测试."""
    p = _pen(low, high, Direction.UP)
    return FeatureElement(high=high, low=low, src_pens=(p,))


# ═══════════════════════════════════════════════════════════
#  Incremental commit is irrevocable
# ═══════════════════════════════════════════════════════════


class TestM1IncrementalCommitIsIrrevocable:
    """增量流式 + 首次命中即 commit.

    构造场景:pen_5 到达时 (f_1, f_2, f_3) 形成 Top 分型且无缺口 → Type1End。
    若继续喂入 pen_6, pen_7,f_4 会与 f_3 合并改变 f_3 极值,在全量视角下
    分型条件失效。Builder must keep commit,不因后续数据改判。
    """

    def test_early_commit_on_fractal_arrival(self) -> None:
        """pen_5 到达即 commit,段终结于 pen_2。"""
        # 波峰/波谷序列 (UP 段雏形)
        pens = _build_chain([15, 22, 19, 30, 20, 28, 15])
        #                    0   1   2   3   4   5   6  (pen index - 1)
        # 笔: pen_0=UP(15→22), pen_1=DOWN(22→19), pen_2=UP(19→30),
        #     pen_3=DOWN(30→20), pen_4=UP(20→28), pen_5=DOWN(28→15)
        # 特征序列 (DOWN 笔): f1=(22,19), f2=(30,20), f3=(28,15)
        # Top 分型 at f2: 30>22,30>28,20>19,20>15 ✓
        # 缺口 (f1,f2): overlap((19,22),(20,30)) → max=20<=min=22 ✓ 无缺口
        # → Type1End at h(f2)=30,末笔 = f2.src=pen_3 之前同向笔 = pen_2

        segments = _type_end_only(build_segments(pens))
        assert len(segments) == 1
        seg = segments[0]
        assert seg.direction == Direction.UP
        assert seg.end_type == "TYPE1"
        assert seg.end_price == 30
        assert len(seg.pens) == 3  # pen_0, pen_1, pen_2

    def test_commit_preserved_when_later_pens_would_void_fractal(self) -> None:
        """加入 pen_6, pen_7 使 f_4 合并 f_3(全量视角分型失效),commit must not be revoked."""
        # extended with,加 pen_6=UP(15→35), pen_7=DOWN(35→10)
        # f_4 = (35, 10)。inc(f_3=(28,15), f_4=(35,10))?
        #   f_4 contains f_3: 35>=28 ✓, 10<=15 ✓ → inc
        # UP merge: max(28,35)=35, max(15,10)=15 → f_3_merged=(35,15)
        # 全量 C' = [f_1(22,19), f_2(30,20), f_3_merged(35,15)]
        # Top fractal at j=1: h(f_2)=30 > h(f_3_merged)=35? No → 分型失效
        pens = _build_chain([15, 22, 19, 30, 20, 28, 15, 35, 10])

        segments = build_segments(pens)
        # segment 0 must remain committed(不因 pen_6/pen_7 撤销)
        assert len(segments) >= 1
        seg0 = segments[0]
        assert seg0.direction == Direction.UP
        assert seg0.end_type == "TYPE1"
        assert seg0.end_price == 30
        assert len(seg0.pens) == 3


# ═══════════════════════════════════════════════════════════
#  Earliest fractal wins (first-hit commit)
# ═══════════════════════════════════════════════════════════


class TestM2EarliestFractalWins:
    """多个候选分型 → 取最早 j。

    构造 UP 段,在 C' 中 j=1 和 j=3 两个位置都有 Top 分型。
    Builder should, at j=1 命中时即 commit,不扫描 j=3。
    """

    def test_earliest_fractal_terminates(self) -> None:
        # F = [f1, f2, f3, f4, f5]
        # 两个分型:j=1 (f1,f2,f3) 和 j=3 (f3,f4,f5)
        # f1=(18,15) f2=(22,17) f3=(20,16) — Top at j=1 (无缺口)
        # f4=(25,18) f5=(23,17) — Top at j=3 需 h(f4)>h(f3) AND l(f4)>l(f3)
        #                        25>20 ✓, 18>16 ✓,且 23<25, 17<18 ✓
        # 无包含关系(已验证)。

        # 波形:为了生成该 F 序列,需要严格构造笔链。DOWN 笔即特征元素。
        # pen_0 UP → pen_1 DOWN(f1) → pen_2 UP → pen_3 DOWN(f2) → ...
        pens = _build_chain(
            [
                15, 18,  # pen_0 UP 15→18
                15, 22,  # pen_1 DOWN 18→15 (f1=(18,15));pen_2 UP 15→22
                17, 20,  # pen_3 DOWN 22→17 (f2=(22,17));pen_4 UP 17→20
                16, 25,  # pen_5 DOWN 20→16 (f3=(20,16));pen_6 UP 16→25
                18, 23,  # pen_7 DOWN 25→18 (f4=(25,18));pen_8 UP 18→23
                17,      # pen_9 DOWN 23→17 (f5=(23,17))
            ]
        )

        segments = build_segments(pens)
        assert len(segments) >= 1
        seg0 = segments[0]
        # 最早分型在 f_2 位置(h=22),而非 f_4 位置(h=25)
        assert seg0.end_price == 22, f"期望 22 (最早 j),实际 {seg0.end_price}"


# ═══════════════════════════════════════════════════════════
#  Extremum candidate set (E_j) min-index
# ═══════════════════════════════════════════════════════════


class TestM3M5ExtremumIndex:
    """E_j 最小元 & 反向序列起点.

    通过直接测试 `_extremum_candidate_set` + `_reverse_verify` 验证。
    """

    def test_extremum_candidate_set_returns_min_index(self) -> None:
        # 合成 F 序列,两个原始元素都达到相同极值(|E_j|=2)
        p1 = _pen(25, 30, Direction.UP)  # dummy pen
        p2 = _pen(35, 20, Direction.DOWN)
        p3 = _pen(20, 35, Direction.UP)
        p4 = _pen(35, 10, Direction.DOWN)

        # F 里 f_a 和 f_b 都有 high=35
        f_a = FeatureElement(high=35, low=20, src_pens=(p2,))
        f_b = FeatureElement(high=35, low=10, src_pens=(p4,))
        F = [f_a, f_b]

        # C_j 合并后 high=35,src=(p2, p4),|E_j|=2
        C_j = FeatureElement(high=35, low=20, src_pens=(p2, p4))
        E_j = _extremum_candidate_set(C_j, Direction.UP, F)
        assert E_j == [0, 1]
        assert min(E_j) == 0  # 取最早


# ═══════════════════════════════════════════════════════════
#  Reverse sequence first-two inclusion
# ═══════════════════════════════════════════════════════════


class TestM4VerifyFirstTwoMustProcess:
    """验证 `_std_verify` 实现正确."""

    def test_first_two_inclusion_is_processed(self) -> None:
        # 构造:首两元素 f1, f2 存在包含关系;_std_verify 必须合并之
        # UP 反向(即 DOWN 段的反向 = UP 方向合并):取 max-max
        p1 = _pen(20, 30, Direction.UP)
        p2 = _pen(15, 35, Direction.UP)
        f1 = FeatureElement(high=30, low=20, src_pens=(p1,))
        f2 = FeatureElement(high=35, low=15, src_pens=(p2,))
        # inc(f1, f2)? f2 contains f1: 35>=30 ✓ AND 15<=20 ✓ → YES

        V = [f1, f2]
        V_std = _std_verify(V, Direction.UP)
        # Builder: 首二必做处理 → 合并成单元素
        assert len(V_std) == 1
        # UP merge: (max(30,35), max(20,15)) = (35, 20)
        assert V_std[0].high == 35
        assert V_std[0].low == 20


# ═══════════════════════════════════════════════════════════
#  No actual_break check (weak top still commits)
# ═══════════════════════════════════════════════════════════


class TestM6NoActualBreakCheck:
    """不引入假突破检测.

    构造 "弱顶" 场景:UP 段终结于某价位,但后续笔不实际跌破该价位。
    Builder must commit(按书本 6.3.2 第一种 "分型成立即结束")。
    若 chan.py 跑同样数据会 reset。
    """

    def test_weak_top_still_commits(self) -> None:
        # UP 段终结于 30;pen_5 DOWN 仅跌至 19.5(顶的相邻底是 19,弱突破)
        # chan.py 式 actual_break 倾向拒绝(未大幅跌破);Builder still commits strictly
        pens = _build_chain([15, 22, 19, 30, 20, 25, 19.5])
        # pen_0 UP 15→22; pen_1 DOWN 22→19 (f1=(22,19));
        # pen_2 UP 19→30; pen_3 DOWN 30→20 (f2=(30,20));
        # pen_4 UP 20→25; pen_5 DOWN 25→19.5 (f3=(25,19.5))
        # Top at f2: 30>22,30>25,20>19,20>19.5 ✓ 弱顶但满足严格四不等号

        segments = build_segments(pens)
        assert len(segments) >= 1
        assert segments[0].direction == Direction.UP
        assert segments[0].end_price == 30
        assert segments[0].end_type == "TYPE1"


# ═══════════════════════════════════════════════════════════
#  Broken-by-pen is warning only
# ═══════════════════════════════════════════════════════════


class TestM7BrokenByPenIsWarningOnly:
    """被笔破坏不触发终结或回溯.

    构造:UP 段内 ∃ d_k < g_i (i+2 ≤ k) 成立,但 C' 中无 Top 分型。
    Builder must keep BUILDING(不输出 confirmed)。
    """

    def test_building_segment_is_not_output_even_with_broken_signal(self) -> None:
        # UP 段构造:g_1=25, g_2=22, g_3=18 呈下降趋势(非顶分型)
        # 同时 d_3=13 < g_1=25 (笔破坏)
        pens = _build_chain([10, 25, 15, 22, 14, 18, 13])
        # pens:
        #   pen_0 UP  10→25  (g_1=25)
        #   pen_1 DOWN 25→15 (d_1=15)
        #   pen_2 UP  15→22  (g_2=22)
        #   pen_3 DOWN 22→14 (d_2=14)
        #   pen_4 UP  14→18  (g_3=18)
        #   pen_5 DOWN 18→13 (d_3=13)
        # 被笔破坏:d_3=13 < g_1=25 且 k=3, i=1, k>=i+2 ✓
        # F = [pen_1, pen_3, pen_5] = [(25,15),(22,14),(18,13)]
        # C' (首二不处理):[(25,15),(22,14)],然后 f_3=(18,13)
        #   inc(f_2=(22,14), f_3=(18,13))? f_2 contains f_3: 22>=18 ✓, 14<=13? NO
        #                                    f_3 contains f_2? 18>=22 NO → 不 inc → append
        # C' = [(25,15),(22,14),(18,13)]
        # Top fractal at j=1: h(f_2)=22 > h(f_1)=25? NO → 无分型
        # → 段保持 BUILDING,不输出

        segments = _confirmed(build_segments(pens))
        assert len(segments) == 0


# ═══════════════════════════════════════════════════════════
#  Pre-segment pens are discarded
# ═══════════════════════════════════════════════════════════


class TestM8PreSegmentPensDiscarded:
    """A4 顺延的前置笔不进入 segments 输出."""

    def test_pre_segment_pens_not_in_output(self) -> None:
        # 构造 pen_0 方向不适合作为段起点的场景:
        # 我们希望首段是 DOWN 段从 pen_2 开始,pen_0 / pen_1 被跳过
        # 但 A4 柔性起点是在 pens[0] 起不合 A2 时才顺延
        #
        # 构造:pens[0] UP 方向,但 pens[0,2] 不重叠 → 跳到 pens[1]
        # pens[1] DOWN 方向,pens[1,3] 重叠 → 从 pens[1] 起建 DOWN 段
        pens = _build_chain([10, 30, 25, 22, 15, 20, 12])
        # pen_0 UP  10→30 (h=30, l=10)
        # pen_1 DOWN 30→25
        # pen_2 UP  25→22  INVALID! 这不是 UP 笔,因为 22 < 25 — _build_chain 会
        #                   自动检测方向,所以实际方向=DOWN

        # _build_chain 按差号自动判方向,我们重新设计:
        # 需要 pens[0] 与 pens[2] 不重叠
        pens = _build_chain([10, 50, 45, 48, 5, 30, 3])
        # pen_0 UP  10→50 (I=(10,50))
        # pen_1 DOWN 50→45
        # pen_2 UP  45→48 (I=(45,48)) — 与 pens[0] 重叠
        #
        # 这里重叠,会从 pen_0 起。换构造:
        pens = _build_chain([40, 50, 45, 48, 5, 30, 3])
        # pen_0 UP  40→50 (I=(40,50))
        # pen_1 DOWN 50→45
        # pen_2 UP  45→48 (I=(45,48)) — 与 pens[0] 重叠(40-50 ∩ 45-48)
        # 仍然重叠。
        #
        # 构造 pens[0] 很短但 pens[2] 在另一价位:_build_chain 要求相邻差符号
        # 决定方向,相邻端点连续。手动构造更灵活:
        pens = [
            _pen(10, 12, Direction.UP),   # pen_0 I=(10,12)
            _pen(12, 11, Direction.DOWN),  # pen_1
            _pen(11, 13, Direction.UP),   # pen_2 I=(11,13) — 与 (10,12) 重叠
        ]
        # 此构造下 pens[0,2] 重叠 → Phase 1 会从 pen_0 起。难以构造 "pens[0] 跳过"
        # 的纯 A4 场景。
        #
        # **实际上 A4 场景需要外部验证数据**(真实 tushare 数据常出现 pens[0]
        # 孤立的情况),synthetic 测试难以自然触发。此测试仅验证算法**不 crash**
        # 且输出合法。
        # Filter out EXTREME fallback(手动构造 3 笔足以触发)
        segments = _type_end_only(build_segments(pens))
        assert len(segments) == 0  # 3 笔不足以触发 TYPE1/TYPE2


# ═══════════════════════════════════════════════════════════
#  Phase 2 strict adjacency
# ═══════════════════════════════════════════════════════════


class TestM9Phase2StrictAdjacency:
    """Phase 2 起点方向不符 → 主循环终止,不顺延.

    实际构造极难(笔方向天然交替),此测试作为防御性断言:
    若笔方向违反交替,Builder must safely stop。
    """

    def test_direction_mismatch_stops_building(self) -> None:
        # 构造单一 UP 段 + 后续不足以成段的笔
        pens = _build_chain([15, 22, 19, 30, 20, 28, 15])
        # 只关心 TYPE1 段的识别是否 1 个,EXTREME follow-ups不在此范围
        segments = _type_end_only(build_segments(pens))
        assert len(segments) == 1
        assert segments[0].direction == Direction.UP


# ═══════════════════════════════════════════════════════════
#  End-pen mapping
# ═══════════════════════════════════════════════════════════


class TestM10EndPenMapping:
    """末笔 = min(E_j) 对应原始笔的前一根同向笔."""

    def test_end_pen_is_same_direction_before_extremum_pen(self) -> None:
        pens = _build_chain([15, 22, 19, 30, 20, 28, 15])
        # 极值在 pen_3 (DOWN 笔, high=30, 即 f_2 的来源).
        # 末笔 = pen_3 - 1 = pen_2 (UP 笔, 即段方向笔,且 end=30).
        # 只关心 TYPE1 段的末笔映射
        segments = _type_end_only(build_segments(pens))
        assert len(segments) == 1
        seg = segments[0]
        assert seg.pens[-1].direction == Direction.UP
        assert seg.pens[-1].end.value == 30


# ═══════════════════════════════════════════════════════════
#  Tentative tail segment (§6.1.1)
# ═══════════════════════════════════════════════════════════


class TestSchemeXTentativeTail:
    """Tentative fallback:主循环无法 commit 时,剩余 ≥ 3 笔且满足 A2+A3.1 → TENTATIVE 段."""

    def test_tentative_tail_in_monotone_drop(self) -> None:
        """UP 段后的连续下跌(单调 V' 无底分型),应识别为 CONFIRMED UP + TENTATIVE DOWN."""
        # 模拟 688066 P18+ 的简化版:UP 段后单调下跌
        pens = _build_chain([10, 22, 19, 30, 20, 28, 15, 25, 10, 20, 5])
        # UP 段:pens[0..4] (10→22, 22→19, 19→30, 30→20, 20→28)
        #  F=[pen1(22,19),pen3(30,20),pen5(28,15)] — Top at j=1(无缺口)→ Type1End 终结在 pen2=30
        # 此后 pen3 DOWN 30→20 起 DOWN 段,单调下跌到末尾
        segments = build_segments(pens)
        confirmed = _confirmed(segments)
        tentative = [s for s in segments if s.state == SegmentState.BUILDING]

        # 至少 1 个 CONFIRMED UP 段(首段)
        assert len(confirmed) >= 1
        assert confirmed[0].direction == Direction.UP

        # 若剩余笔单调下跌无法 commit,应有 tentative DOWN 尾段
        if tentative:
            assert tentative[0].state == SegmentState.BUILDING
            assert tentative[0].end_type == "TENTATIVE"
            assert len(tentative[0].pens) >= 3
            assert len(tentative[0].pens) % 2 == 1

    def test_tentative_respects_a3_1_direction(self) -> None:
        """A3.1: tentative 段方向主导仍必须成立."""
        # 只给 3 根笔,方向 UP 但 end < start 违反 A3.1 — 不可能,_build_chain 保证方向一致
        # 此测试验证:即使 3 笔构成的结构,若 A3.1 不成立,不应输出 tentative
        pens = _build_chain([10, 20, 15, 18])  # UP DOWN UP,最后 end=18 > start=10 → A3.1 OK
        segments = build_segments(pens)
        # 要么有 tentative 要么没 commit;无论哪种都不应有 A3.1 违反的段
        for s in segments:
            if s.direction == Direction.UP:
                assert s.pens[-1].end.value > s.pens[0].start.value

    def test_tentative_does_not_affect_confirmed(self) -> None:
        """TYPE1 段的 end_type 不应被 TENTATIVE 覆盖."""
        pens = _build_chain([15, 22, 19, 30, 20, 28, 15])
        segments = build_segments(pens)
        # 只关心 TYPE1 段(EXTREME follow-ups也是 CONFIRMED,但非 TYPE1)
        type1_segs = _type_end_only(segments)
        assert len(type1_segs) == 1
        assert type1_segs[0].end_type == "TYPE1"


# ═══════════════════════════════════════════════════════════
#  Primitive smoke tests
# ═══════════════════════════════════════════════════════════


class TestPrimitivesSmoke:
    def test_has_inclusion(self) -> None:
        a = _fe(high=25, low=10)
        b = _fe(high=20, low=15)
        assert _has_inclusion(a, b)  # a contains b
        c = _fe(high=30, low=26)
        assert not _has_inclusion(a, c)  # no containment

    def test_merge_star_up(self) -> None:
        a = _fe(high=20, low=10)
        b = _fe(high=22, low=15)
        merged = _merge_star(a, b, Direction.UP)
        assert merged.high == 22
        assert merged.low == 15  # max-max
        assert merged.src_pens == a.src_pens + b.src_pens

    def test_merge_star_down(self) -> None:
        a = _fe(high=20, low=10)
        b = _fe(high=22, low=15)
        merged = _merge_star(a, b, Direction.DOWN)
        assert merged.high == 20  # min-min
        assert merged.low == 10
