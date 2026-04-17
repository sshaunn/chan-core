"""ChanEngine facade, snapshot dataclasses, and AnalysisResult."""

from dataclasses import dataclass

from chan_core.common.kline import MergedKLine, RawKLine
from chan_core.common.types import Direction, SegmentState, TrendType
from chan_core.config import ChanConfig
from chan_core.structure._fractal import Fractal
from chan_core.structure._pen import Pen


@dataclass(frozen=True)
class CompletionTrace:
    """Full evidence chain for structure_complete."""

    exit_seq_ids: tuple[str, ...]
    i_star: int | None
    t_end: str | None
    awaiting_new_pivot: bool


@dataclass(frozen=True)
class SegmentSnapshot:
    """Immutable snapshot of a segment.

    See `structure/README.md` S04–S06 for the full end_type semantics.
    end_type ∈ {TYPE1, TYPE2, EXTENDED, EXTREME, TENTATIVE}; only TENTATIVE
    segments have state=BUILDING.
    """

    pens: tuple[Pen, ...]
    direction: Direction
    state: SegmentState
    high: float
    low: float
    end_price: float | None = None
    end_type: str | None = None


@dataclass(frozen=True)
class PivotSnapshot:
    """Immutable snapshot of a pivot (中枢)."""

    zd: float
    zg: float
    dd: float
    gg: float
    components: tuple[object, ...]
    entry_time: str
    exit_time: str


@dataclass(frozen=True)
class TrendSnapshot:
    """Immutable snapshot of a trend, including completion trace."""

    pivots: tuple[PivotSnapshot, ...]
    trend_type: TrendType | None
    structure_complete: bool
    completion: CompletionTrace


@dataclass(frozen=True)
class AnalysisResult:
    """Full-chain analysis output — all fields immutable tuples.

    Level hierarchy:
      L0: pens → l0_pivots; L0 trend = segment (complete iff CONFIRMED)
      L1: confirmed segments → l1_pivots → l1_trends (complete via ExitSeq+i*)
    """

    merged_klines: tuple[MergedKLine, ...]
    fractals: tuple[Fractal, ...]
    pens: tuple[Pen, ...]
    segments: tuple[SegmentSnapshot, ...]
    # L0: pen-level pivots
    l0_pivots: tuple[PivotSnapshot, ...]
    # L1: segment-level pivots and trends
    l1_pivots: tuple[PivotSnapshot, ...]
    l1_trends: tuple[TrendSnapshot, ...]

    # Backward compat aliases
    @property
    def pivots(self) -> tuple[PivotSnapshot, ...]:
        return self.l0_pivots

    @property
    def trends(self) -> tuple[TrendSnapshot, ...]:
        return self.l1_trends


class ChanEngine:
    """Facade: orchestrates the full structure-layer pipeline."""

    def __init__(self, config: ChanConfig | None = None) -> None:
        self._config = config or ChanConfig()

    def analyze(self, klines: list[RawKLine]) -> AnalysisResult:
        """Run the full pipeline and return an immutable result."""
        from chan_core.structure._completion import structure_complete_by_pivot
        from chan_core.structure._fractal import find_fractals
        from chan_core.structure._merge import merge_inclusive
        from chan_core.structure._pen import build_confirmed, build_pens
        from chan_core.structure._pivot import search_pivots
        from chan_core.structure._segment import build_segments
        from chan_core.structure._trend import classify_trend

        # Step 1-3: K-lines → merged → fractals → pens
        merged = merge_inclusive(klines)
        fractals = find_fractals(merged)
        confirmed = build_confirmed(fractals)
        pens = build_pens(confirmed)

        # Step 4: Segments (L0 trends)
        segments = build_segments(pens)

        # Step 5: L0 pivots (pen-level)
        l0_pivot_builders = search_pivots(pens)
        l0_pivot_snaps = tuple(pb.to_snapshot() for pb in l0_pivot_builders)

        # Step 6: L1 pivots (segment-level, only CONFIRMED segments)
        confirmed_segs = [s for s in segments if s.state == SegmentState.CONFIRMED]
        l1_pivot_builders = search_pivots(confirmed_segs)
        l1_pivot_snaps = tuple(pb.to_snapshot() for pb in l1_pivot_builders)

        # Step 7: L1 trends (segment-level structure_complete via ExitSeq+i*)
        l1_trends: list[TrendSnapshot] = []
        processed: list[int] = []

        for pi, pb in enumerate(l1_pivot_builders):
            trace = structure_complete_by_pivot([pb], confirmed_segs)

            if trace.i_star is not None:
                trend_pivots = processed + [pi]
                snap_pivots = [l1_pivot_snaps[j] for j in trend_pivots]
                trend_type = classify_trend(snap_pivots, True)
                l1_trends.append(TrendSnapshot(
                    pivots=tuple(snap_pivots),
                    trend_type=trend_type,
                    structure_complete=True,
                    completion=trace,
                ))
                processed = []
            else:
                processed.append(pi)

        if processed:
            last_pb = l1_pivot_builders[processed[-1]]
            trace = structure_complete_by_pivot([last_pb], confirmed_segs)
            snap_pivots = [l1_pivot_snaps[j] for j in processed]
            l1_trends.append(TrendSnapshot(
                pivots=tuple(snap_pivots),
                trend_type=None,
                structure_complete=False,
                completion=trace,
            ))

        if not l1_pivot_builders:
            empty_trace = CompletionTrace(
                exit_seq_ids=(), i_star=None,
                t_end=None, awaiting_new_pivot=False,
            )
            l1_trends.append(TrendSnapshot(
                pivots=(),
                trend_type=None,
                structure_complete=False,
                completion=empty_trace,
            ))

        return AnalysisResult(
            merged_klines=tuple(merged),
            fractals=tuple(fractals),
            pens=tuple(pens),
            segments=tuple(segments),
            l0_pivots=l0_pivot_snaps,
            l1_pivots=l1_pivot_snaps,
            l1_trends=tuple(l1_trends),
        )

    def feed(self, kline: RawKLine) -> None:
        """Incremental feed for real-time scenarios (experimental)."""
        raise NotImplementedError

    def snapshot(self) -> AnalysisResult:
        """Return current-state snapshot (requires prior feed calls)."""
        raise NotImplementedError
