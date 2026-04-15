"""Enumerations shared across structure and signal layers."""

from enum import Enum


class Direction(Enum):
    """Merge direction / pen direction."""

    UP = "UP"
    DOWN = "DOWN"


class FractalType(Enum):
    """Fractal polarity."""

    TOP = "TOP"
    BOT = "BOT"


class SegmentState(Enum):
    """Segment lifecycle state."""

    BUILDING = "BUILDING"
    CONFIRMED = "CONFIRMED"


class TrendType(Enum):
    """Trend classification (requires structure_complete)."""

    CONSOLIDATION = "CONSOLIDATION"
    UP_TREND = "UP_TREND"
    DOWN_TREND = "DOWN_TREND"
