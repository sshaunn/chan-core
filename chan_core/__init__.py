"""chan-core: structure-layer computation engine."""

from chan_core.common.kline import MergedKLine, RawKLine
from chan_core.common.types import Direction, FractalType, TrendType
from chan_core.config import ChanConfig
from chan_core.engine import (
    AnalysisResult,
    ChanEngine,
    CompletionTrace,
    PivotSnapshot,
    SegmentSnapshot,
    TrendSnapshot,
)
from chan_core.structure._fractal import Fractal
from chan_core.structure._pen import Pen

__all__ = [
    "ChanEngine",
    "ChanConfig",
    "AnalysisResult",
    "Direction",
    "FractalType",
    "TrendType",
    "RawKLine",
    "MergedKLine",
    "Fractal",
    "Pen",
    "SegmentSnapshot",
    "PivotSnapshot",
    "TrendSnapshot",
    "CompletionTrace",
]

__version__ = "0.1.0"
