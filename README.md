# chan-core

Chan Theory (缠论) structure-layer computation engine.

缠论结构层计算引擎。

## What is this / 这是什么

A Python implementation of the frozen structure definitions (S01–S12) from Chan Theory (*"Teaching You to Trade"* by Chan Zhong Shuo Chan). Covers the full pipeline from raw K-lines to `structure_complete`, with no signal-layer dependencies.

基于《教你炒股票》原文的缠论结构层冻结定义（S01–S12）的 Python 实现。覆盖从原始K线到 `structure_complete` 的完整链路，不依赖任何信号层概念。

```
RawKLine → MergedKLine → Fractal → Pen → Segment → Pivot → Trend → structure_complete
原始K线  →  标准化K线  →  分型  →  笔  →  线段  →  中枢  → 走势 →   走势完成判定
```

## Structure Definitions / 结构定义

See **[`chan_core/structure/README.md`](chan_core/structure/README.md)** for detailed documentation of each structural concept (S01–S12).

各结构形态的详细定义见 **[`chan_core/structure/README.md`](chan_core/structure/README.md)**。

## Requirements / 环境要求

- Python 3.12+

## Installation / 安装

```bash
pip install -e ".[dev]"
```

## Usage / 使用

```python
from chan_core import ChanEngine, RawKLine

klines = [
    RawKLine(high=10.0, low=8.0, timestamp="20250101"),
    RawKLine(high=12.0, low=9.0, timestamp="20250102"),
    # ...
]

engine = ChanEngine()
result = engine.analyze(klines)

print(f"Merged K-lines: {len(result.merged_klines)}")
print(f"Fractals: {len(result.fractals)}")
print(f"Pens: {len(result.pens)}")
print(f"Segments: {len(result.segments)}")
print(f"L0 Pivots (pen-level): {len(result.l0_pivots)}")
print(f"L1 Pivots (segment-level): {len(result.l1_pivots)}")
for trend in result.l1_trends:
    print(f"L1 Trend: {trend.trend_type}, complete={trend.structure_complete}")
```

## Testing / 测试

```bash
# Run all tests
pytest

# With coverage
pytest --cov=chan_core

# Type checking
mypy chan_core --strict
```

## Project Structure / 项目结构

```
chan_core/
├── __init__.py              # Public API (__all__, __version__)
├── engine.py                # ChanEngine facade + snapshot dataclasses
├── config.py                # ChanConfig (frozen dataclass tree)
├── common/                  # Shared types & utilities
│   ├── types.py             # Direction, FractalType, SegmentState, TrendType
│   ├── kline.py             # RawKLine, MergedKLine
│   ├── math_utils.py        # overlap, strict_overlap
│   └── protocols.py         # SubTrendLike Protocol (L1+ generalisation)
├── structure/               # Frozen structure layer (S01–S12)
│   ├── README.md            # ← Detailed structural definitions
│   ├── _merge.py            # S01: K-line inclusion merge
│   ├── _fractal.py          # S02: Fractal detection
│   ├── _pen.py              # S03: Pen (confirmed algorithm)
│   ├── _segment.py          # S04–S06: Segment builder (three-stage + Pass 2)
│   ├── _feature_sequence.py # S04–S06: Feature sequence + EigenFX state machine
│   ├── _pivot.py            # S07–S09: Pivot + extension/leave + search
│   ├── _trend.py            # S10: Trend classification
│   └── _completion.py       # S11–S12: Level recursion + structure_complete
└── signal/                  # Signal layer (future, currently empty)
```

## License / 许可证

Apache License 2.0
