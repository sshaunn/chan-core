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

A segment is formed by ≥ 3 pens (odd count), where the first and third pens overlap. Termination is determined by feature sequence fractals (Type1End / Type2End).

线段由 ≥ 3 笔（奇数）组成，前三笔必须有重叠。终结由特征序列分型决定。

**Feature sequence / 特征序列**: Opposite-direction pens within the segment, treated as virtual K-lines and merged using the same inclusion rules.

特征序列为线段内反向笔，视为虚拟K线，使用相同的包含合并规则处理。

**Type1End / 第一类终结**: Feature sequence fractal exists, AND the fractal element overlaps with its predecessor.

特征序列分型成立，且分型元素与前一元素有重叠。

**Type2End / 第二类终结**: Feature sequence fractal exists, NO overlap (gap), AND a verification sequence in the same direction as the segment produces a reverse fractal.

特征序列分型成立，无重叠（缺口），且同向验证序列产生反向分型。

**State machine / 状态机**: `BUILDING → CONFIRMED` (irreversible).

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
next_search_start = leave_pen_index + 1
```

The leave pen belongs to the connection segment between two pivots (`a + Z₁ + b + Z₂ + c`), not to the new pivot. Search for the next pivot starts from the pen **after** the leave pen.

离开笔属于两个中枢之间的连接段，不属于新中枢。新中枢搜索从离开笔的下一根笔开始。

---

## S10 — Trend Classification / 走势分类

**Module**: [`_trend.py`](_trend.py)

Requires `structure_complete = True`. Classification is purely structural, no divergence or buy/sell signals.

前提是 `structure_complete = True`。分类纯粹基于结构，不依赖背驰或买卖点。

| Type | Condition |
|------|-----------|
| **Consolidation / 盘整** | 1 pivot |
| **Up Trend / 上涨趋势** | ≥ 2 pivots, `DD_{k+1} > GG_k` for all k |
| **Down Trend / 下跌趋势** | ≥ 2 pivots, `GG_{k+1} < DD_k` for all k |

---

## S11 — Level Recursion / 级别递归

Levels are produced by structural recursion, separated from time periods.

级别由结构递归产生，与时间周期分离。

| Level | Trend | Pivot components | Completion |
|-------|-------|-----------------|------------|
| L0 | Segment | Pen | `SegState = CONFIRMED` |
| L1 | Composed of L0 pivots/trends | Confirmed segments | `structure_complete_L1` |
| Lk | Composed of L(k-1) | L(k-1) completed trends | `structure_complete_Lk` |

---

## S12 — structure_complete / 走势完成判定

**Module**: [`_completion.py`](_completion.py)

Answers only: *"Is the trend structurally finished?"* Does not depend on divergence, buy/sell points, or any signal-layer concept.

只回答"走势结构是否走完"，不依赖背驰、买卖点或任何信号层概念。

**ExitSeq**: Sub-trends after the last pivot that satisfy the leave condition, collected in time order.

离开序列：最后一个中枢之后满足离开条件的次级别走势，按时间顺序收集。

**i\***: First index where three consecutive ExitSeq elements form a new pivot (`ZD < ZG`).

首个满足三段形成新中枢的位置。

**t_end**: `max(t_end(V))` for all sub-trends V that end before `W_{i*}` starts.

**awaiting_new_pivot**: ExitSeq is non-empty but `i*` does not exist. Observation state, not a signal.

离开序列非空但 i* 不存在。结构观察状态，不是信号。
