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
    """Immutable snapshot of a segment."""

    pens: tuple[Pen, ...]
    direction: Direction
    state: SegmentState
    high: float
    low: float


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
    """Full-chain analysis output — all fields immutable tuples."""

    merged_klines: tuple[MergedKLine, ...]
    fractals: tuple[Fractal, ...]
    pens: tuple[Pen, ...]
    segments: tuple[SegmentSnapshot, ...]
    pivots: tuple[PivotSnapshot, ...]
    trends: tuple[TrendSnapshot, ...]


class ChanEngine:
    """Facade: orchestrates the full structure-layer pipeline."""

    def __init__(self, config: ChanConfig | None = None) -> None:
        self._config = config or ChanConfig()

    def analyze(self, klines: list[RawKLine]) -> AnalysisResult:
        """Run the full pipeline and return an immutable result."""
        from chan_core.structure._completion import structure_complete_l0
        from chan_core.structure._fractal import find_fractals
        from chan_core.structure._merge import merge_inclusive
        from chan_core.structure._pen import build_confirmed, build_pens
        from chan_core.structure._pivot import search_pivots
        from chan_core.structure._segment import build_segments
        from chan_core.structure._trend import TrendBuilder, classify_trend

        # Step 1: Merge inclusive
        merged = merge_inclusive(klines)

        # Step 2: Find fractals
        fractals = find_fractals(merged)

        # Step 3: Build pens
        confirmed = build_confirmed(fractals)
        pens = build_pens(confirmed)

        # Step 4: Build segments
        segments = build_segments(pens)

        # Step 5: Search pivots (L0: pens as sub-trends)
        pivot_builders = search_pivots(pens)
        all_pivot_snaps = [pb.to_snapshot() for pb in pivot_builders]

        # Step 6: Build trends by analyzing each pivot's exit sequence
        trends: list[TrendSnapshot] = []
        processed_pivots: list[int] = []  # indices of pivots in current trend

        for pi, pb in enumerate(pivot_builders):
            # Check structure_complete for the trend ending at this pivot
            trace = structure_complete_l0([pb], pens)

            if trace.i_star is not None:
                # This pivot's exit sequence forms a new pivot → trend complete
                trend_pivots = processed_pivots + [pi]
                snap_pivots = [all_pivot_snaps[j] for j in trend_pivots]
                is_complete = True
                trend_type = classify_trend(snap_pivots, is_complete)
                trends.append(TrendSnapshot(
                    pivots=tuple(snap_pivots),
                    trend_type=trend_type,
                    structure_complete=True,
                    completion=trace,
                ))
                processed_pivots = []
            else:
                processed_pivots.append(pi)

        # Remaining pivots form an incomplete trend
        if processed_pivots:
            last_pb = pivot_builders[processed_pivots[-1]]
            trace = structure_complete_l0([last_pb], pens)
            snap_pivots = [all_pivot_snaps[j] for j in processed_pivots]
            trends.append(TrendSnapshot(
                pivots=tuple(snap_pivots),
                trend_type=None,
                structure_complete=False,
                completion=trace,
            ))

        # If no pivots at all, create a single empty trend
        if not pivot_builders:
            empty_trace = CompletionTrace(
                exit_seq_ids=(), i_star=None,
                t_end=None, awaiting_new_pivot=False,
            )
            trends.append(TrendSnapshot(
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
            pivots=tuple(all_pivot_snaps),
            trends=tuple(trends),
        )

    def feed(self, kline: RawKLine) -> None:
        """Incremental feed for real-time scenarios (experimental)."""
        raise NotImplementedError

    def snapshot(self) -> AnalysisResult:
        """Return current-state snapshot (requires prior feed calls)."""
        raise NotImplementedError
