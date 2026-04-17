# Structure Layer / 结构层

> Frozen structure definitions (S01–S12) from *"Chan Theory Structure Baseline"*.
> 冻结的结构层定义（S01–S12），源自《缠论结构基线最终稿》。

---

## Pipeline / 处理链路

```
RawKLine → [_merge] → MergedKLine → [_fractal] → Fractal → [_pen] → Pen
  → [_segment] → Segment → [_pivot] → Pivot → [_trend] → Trend
                                                 ↓
                                          [_completion] → structure_complete
```

---

## S01 — K-Line Merge / K线包含关系归并

**Module**: [`_merge.py`](_merge.py)

Standardises raw K-lines by merging adjacent bars that have an inclusion relationship. Single-pass, left-to-right, no backtracking.

将存在包含关系的相邻K线合并为标准化K线。严格从左到右单遍处理，不回溯。

**Inclusion rule / 包含规则**:

```
inc(A, B) ⟺ (A.high ≥ B.high ∧ A.low ≤ B.low) ∨ (B.high ≥ A.high ∧ B.low ≤ A.low)
```

**Merge direction / 合并方向**:
- UP: `max(highs), max(lows)` — 向上取高高
- DOWN: `min(highs), min(lows)` — 向下取低低
- No prior bar: default UP — 无前置K线时默认向上

**Post-condition / 后置条件**: No adjacent merged bars have inclusion.
合并后相邻标准K线不存在包含关系。

---

## S02 — Fractal / 分型

**Module**: [`_fractal.py`](_fractal.py)

Detects top and bottom fractals on the merged K-line sequence using a sliding window of 3.

在标准化K线序列上用滑动窗口（size=3）检测顶分型和底分型。

**Top fractal / 顶分型**:

```
Top(i) ⟺ h_i > h_{i-1} ∧ h_i > h_{i+1} ∧ l_i > l_{i-1} ∧ l_i > l_{i+1}
```

**Bottom fractal / 底分型**:

```
Bot(i) ⟺ l_i < l_{i-1} ∧ l_i < l_{i+1} ∧ h_i < h_{i-1} ∧ h_i < h_{i+1}
```

**Key constraint / 关键约束**: Strict inequality on all four conditions. Equal values do not qualify.
四个条件全部使用严格不等号，相等不成立。

Only `high` and `low` are used. Open/close prices are not involved.
仅使用最高价和最低价，开盘价/收盘价不参与判定。

---

## S03 — Pen / 笔

**Module**: [`_pen.py`](_pen.py)

Builds pens (strokes) from fractal pairs using the confirmed-list algorithm.

使用 confirmed 列表算法从分型对中构建笔。

**Conditions / 成立条件**:

| Condition | Definition |
|-----------|-----------|
| **C1** (independence) | `KLines(F_a) ∩ KLines(F_b) = ∅` — merged index gap ≥ 3 |
| **C2** (raw distance) | ≥ 2 raw K-lines between the two extreme bars (raw index diff ≥ 3) |
| **C4** (price validity) | `val(top) > val(bot)` |

C1 checks structural independence on **standard K-lines**.
C2 checks distance on **raw K-lines**. Both dimensions must pass.

C1 在标准K线维度检查结构独立性。C2 在原始K线维度检查间距。两个维度都必须满足。

**Confirmed-list algorithm / confirmed 列表算法**:
- Same-type adjacent fractals: keep the more extreme (top→higher, bot→lower)
- Opposite-type: append only if C1 ∧ C2 ∧ C4

**Properties / 性质**:
- Zero-gap: `pen[k].end == pen[k+1].start`
- Direction strictly alternates
- 笔首尾相连（零断裂），方向严格交替

---

## S04–S06 — Segment / 线段

**Modules**: [`_segment.py`](_segment.py), [`_feature_sequence.py`](_feature_sequence.py)

A segment is formed by ≥ 3 pens (odd count), first and third pens overlapping, direction determined by the first pen. Segment identification uses a three-stage recursive procedure matching Book §6.3.4's three worked examples.

线段由 ≥ 3 笔（奇数）组成，前三笔重叠，方向由首笔决定。段识别采用三阶段递进流程，对应书本 §6.3.4 三个实战案例。

**Three iron rules / 三铁则** (§6.1.1):

| Rule | Condition |
|------|-----------|
| A1 | `|S| = 2k + 1, k ≥ 1` |
| A2 | `I(B_1) ∩ I(B_3) ≠ ∅` |
| A3 | `direction(S) = direction(B_1)` |

**A3.1 Directional dominance / 方向主导** (§6.1.1 + 78 课): Segment trajectory must align with direction — UP needs `end > start`, DOWN needs `end < start`.

### Three-stage recursive identification / 三阶段递进识别

**Stage B/C — Feature sequence method / 特征序列法** (§6.2–§6.3):

`EigenFX` incremental state machine with O(1) amortised per pen:

- **Feature sequence F** / 特征序列: opposite-direction pens in segment, treated as virtual K-lines
- **Primary standardisation C'** / 主序列标准化 (§6.2.3): first two elements never merge; from the 3rd onwards, merge with stack top under directional rule (UP = high-high, DOWN = low-low)
- **Type1End / 第一类终结** (§6.3.2 case 1): Main fractal with NO gap at `(C'_{j-1}, C'_j)` → segment ends at the fractal extremum
- **Type2End / 第二类终结** (§6.3.2 case 2): Main fractal WITH gap, plus reverse verification on verification sequence V' (suffix of F starting from extremum anchor), where V' uses OPPOSITE merge direction AND processes first-two inclusion. Reverse fractal in V' → segment ends

First-hit commit (`j` ascending, irreversible). Pending state during Type2End verification allows incremental reverse sequence growth.

**Stage A — Extreme fallback / 极值法兜底** (§6.3.4 case 1):

If Stage B/C fails (common in monotonic data where reverse fractal cannot form), scan window for the most-extreme top/bot pen, use it as segment endpoint anchor, re-verify with three iron rules + A3.1. Succeeds → `end_type = EXTREME`.

特征序列法失败时（单调趋势无反向分型），扫窗口价格极值作为段终点锚,三铁则 + A3.1 验证。

**Constructive fallback / 构造性兜底** (§6.1.1 "3-pen segment"):

If both Stage B/C and Stage A fail, output the longest valid odd-length pen chain with A2 + A3.1. `state = BUILDING`, `end_type = TENTATIVE` — tail-end segments not yet fully terminated.

### Pass 2 — Segment extension / 段合并延伸 (§6.3.3)

After Pass 1 produces a segment sequence, scan each adjacent pair `(S_k, S_{k+1})`:

1. Search within `S_{k+1}.pens[1:]` for a legal reverse segment `R` with direction = `S_k.direction` (CONFIRMED only; TENTATIVE rejected).
2. If `R.end_price` strictly exceeds `S_k.end_price` in `S_k`'s direction → absorb: `S_k^new = S_k.pens + [S_{k+1}.pens[0]] + R.pens`.
3. Re-verify A1 + A3.1 on `S_k^new`. Remaining pens re-identified with strict starting direction.
4. `end_type = EXTENDED`. `k` stays for chain absorption.

书本 §6.3.3 "如果缺口被封闭，则原线段延伸" 的直接实装。

### Segment output / 段输出

Each segment is emitted as a `SegmentSnapshot` with `end_type ∈ {TYPE1, TYPE2, EXTREME, EXTENDED, TENTATIVE}`:

| end_type | Source | state |
|----------|--------|-------|
| `TYPE1` | §6.3.2 case 1 (no gap) | CONFIRMED |
| `TYPE2` | §6.3.2 case 2 (gap + reverse verified) | CONFIRMED |
| `EXTREME` | §6.3.4 case 1 (extreme fallback) | CONFIRMED |
| `EXTENDED` | §6.3.3 (Pass 2 absorption) | CONFIRMED |
| `TENTATIVE` | §6.1.1 (constructive fallback) | **BUILDING** |

Downstream (pivot, trend) uses only CONFIRMED segments; TENTATIVE is for tail-end transparency.

**Broken by pen / 被笔破坏** (§6.3.3): warning only, NOT a termination trigger. Available as metadata for signal layer.

### Complexity / 复杂度

- `EigenFX.add`: O(1) amortised (based on C'/V' stack invariants)
- Single segment identification: O(N)
- `build_segments` main loop: **O(N²) worst**, O(N) typical on real data
- Measured: 000001 six-year, 1518 raw K-lines / 149 pens, **0.6 ms** total

---

## S07–S08 — Pivot / 中枢

**Module**: [`_pivot.py`](_pivot.py)

A pivot forms when three consecutive sub-trends have strict overlap.

三个连续次级别走势产生严格重叠时，中枢成立。

**Formation / 形成**:

```
ZG = min(highs),  ZD = max(lows)
Pivot forms ⟺ ZD < ZG (strict)
```

**Four boundaries / 四边界**:

| Boundary | Definition | Updates? |
|----------|-----------|----------|
| ZG | `min(highs)` of initial 3 | Never |
| ZD | `max(lows)` of initial 3 | Never |
| GG | `max(highs)` of all components | On extension |
| DD | `min(lows)` of all components | On extension |

Invariant: `DD ≤ ZD < ZG ≤ GG`

**Extension / 延伸**: `[pen.low, pen.high] ∩ [ZD, ZG] ≠ ∅` → updates GG/DD, keeps ZD/ZG.

**Leave / 离开**: No overlap with `[ZD, ZG]`. Direction: UP if `pen.low > ZG`, DOWN if `pen.high < ZD`.

---

## S09 — Pivot Search Start / 中枢搜索起点

**Module**: [`_pivot.py`](_pivot.py)

```
next_search_start = leave_pen_index
```

The leave pen does not overlap `[ZD, ZG]` of the current pivot, so it belongs to the next structure. Search for the next pivot starts from the **leave pen itself** (it can become the first pen of the next pivot).

离开笔与当前中枢核心区间无重叠,属于新结构起始。新中枢搜索从离开笔本身开始。

---

## S10 — Trend Classification / 走势分类

**Module**: [`_trend.py`](_trend.py)

Requires `structure_complete = True`. Classification is purely structural, no divergence or buy/sell signals.

前提是 `structure_complete = True`。分类纯粹基于结构，不依赖背驰或买卖点。

| Type | Condition |
|------|-----------|
| **Consolidation / 盘整** | 1 pivot |
| **Up Trend / 上涨趋势** | ≥ 2 pivots, `ZD_{k+1} > ZG_k` for all k (core intervals) |
| **Down Trend / 下跌趋势** | ≥ 2 pivots, `ZG_{k+1} < ZD_k` for all k (core intervals) |

---

## S11 — Level Recursion / 级别递归

Levels are produced by structural recursion, separated from time periods.

级别由结构递归产生,与时间周期分离。

| Level | Trend (走势) | Pivot components (中枢构成) | Completion (完成判定) |
|-------|-------------|---------------------------|---------------------|
| L0 | Segment | Pen | `SegState = CONFIRMED` |
| L1 | Composed of confirmed segments | Confirmed segments | `structure_complete_by_pivot` (ExitSeq + i*) |
| Lk | Composed of L(k-1) completed trends | L(k-1) completed trends | Same ExitSeq + i* formula |

**Implementation status**: L0 and L1 are fully implemented. L2+ awaits L1 completed trends.

**实装状态**: L0 和 L1 已完整实现。L2+ 待 L1 产出已完成走势后递归构建。

---

## S12 — structure_complete / 走势完成判定

**Module**: [`_completion.py`](_completion.py)

Answers only: *"Is the trend structurally finished?"* Does not depend on divergence, buy/sell points, or any signal-layer concept.

只回答"走势结构是否走完",不依赖背驰、买卖点或任何信号层概念。

**L0**: `structure_complete_l0(segment) -> bool` — simply checks `SegState == CONFIRMED`. No pivots or ExitSeq needed.

**L1+**: `structure_complete_by_pivot(pivots, sub_trends) -> CompletionTrace` — uses ExitSeq + i* formula:

**ExitSeq**: Sub-trends after the last pivot that satisfy the leave condition, collected in time order.

**i\***: First index where three consecutive ExitSeq elements form a new pivot (`ZD < ZG`).

**t_end**: `max(t_end(V))` for all sub-trends V where `t_end(V) < t_start(W_{i*})` (strict `<`).

**awaiting_new_pivot**: ExitSeq is non-empty but `i*` does not exist. Observation state, not a signal.
