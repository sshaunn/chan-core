"""Configuration tree — frozen dataclasses, no mutable state."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class StructureConfig:
    """Structure-layer configuration.

    Frozen definitions are module-level constants, not configurable here.
    """

    pass


@dataclass(frozen=True)
class SignalConfig:
    """Signal-layer configuration — future extension point."""

    pass


@dataclass(frozen=True)
class ChanConfig:
    """Unified configuration entry point."""

    structure: StructureConfig = field(default_factory=StructureConfig)
    signal: SignalConfig = field(default_factory=SignalConfig)
