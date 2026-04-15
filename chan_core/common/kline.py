"""RawKLine and MergedKLine value objects."""

from dataclasses import dataclass


@dataclass(frozen=True)
class RawKLine:
    """Original candlestick bar — immutable once constructed.

    Fields:
        high: highest price
        low:  lowest price
        timestamp: time identifier (must be closed bar)
    """

    high: float
    low: float
    timestamp: str

    def __post_init__(self) -> None:
        if self.low > self.high:
            raise ValueError(
                f"low ({self.low}) must be <= high ({self.high})"
            )

    @property
    def interval(self) -> tuple[float, float]:
        return (self.low, self.high)


@dataclass(frozen=True)
class MergedKLine:
    """Standardised K-line after inclusion merge — immutable.

    Fields:
        high: highest price (may come from merge)
        low:  lowest price (may come from merge)
        timestamp: time identifier of the *last* raw bar in this group
        source_indices: indices of all raw bars merged into this one
    """

    high: float
    low: float
    timestamp: str
    source_indices: tuple[int, ...]

    def __post_init__(self) -> None:
        if self.low > self.high:
            raise ValueError(
                f"low ({self.low}) must be <= high ({self.high})"
            )

    @property
    def interval(self) -> tuple[float, float]:
        return (self.low, self.high)
