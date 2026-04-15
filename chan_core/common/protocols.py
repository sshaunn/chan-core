"""Structural protocols for L1+ generalisation."""

from typing import Protocol, runtime_checkable


@runtime_checkable
class SubTrendLike(Protocol):
    """Anything that can serve as a sub-trend component of a pivot.

    At L0 this is Pen; at L1+ this is SegmentSnapshot.
    """

    @property
    def high(self) -> float: ...

    @property
    def low(self) -> float: ...
