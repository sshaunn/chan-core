"""Task 00 tests: skeleton, config, engine, public API."""

import pytest

import chan_core
from chan_core import ChanConfig, ChanEngine, RawKLine
from chan_core.config import SignalConfig, StructureConfig


# ── Positive ──────────────────────────────────────────────


def test_config_zero_args() -> None:
    cfg = ChanConfig()
    assert isinstance(cfg.structure, StructureConfig)
    assert isinstance(cfg.signal, SignalConfig)


def test_import_chan_engine() -> None:
    from chan_core import ChanEngine, ChanConfig  # noqa: F811

    assert ChanEngine is not None
    assert ChanConfig is not None


def test_all_importable() -> None:
    for name in chan_core.__all__:
        obj = getattr(chan_core, name, None)
        assert obj is not None, f"{name} listed in __all__ but not importable"


def test_version_exists() -> None:
    assert hasattr(chan_core, "__version__")
    assert isinstance(chan_core.__version__, str)


def test_engine_accepts_config() -> None:
    cfg = ChanConfig()
    engine = ChanEngine(config=cfg)
    assert engine is not None


def test_engine_default_config() -> None:
    engine = ChanEngine()
    assert engine is not None


# ── Negative / NotImplementedError ────────────────────────


def test_engine_analyze_works() -> None:
    engine = ChanEngine()
    result = engine.analyze([])
    assert result.merged_klines == ()
    assert result.pens == ()


def test_engine_feed_not_implemented() -> None:
    engine = ChanEngine()
    with pytest.raises(NotImplementedError):
        engine.feed(RawKLine(high=10.0, low=5.0, timestamp="20250101"))


def test_engine_snapshot_not_implemented() -> None:
    engine = ChanEngine()
    with pytest.raises(NotImplementedError):
        engine.snapshot()


# ── Immutability ──────────────────────────────────────────


def test_config_immutable() -> None:
    cfg = ChanConfig()
    with pytest.raises(AttributeError):
        cfg.structure = StructureConfig()  # type: ignore[misc]


def test_structure_config_immutable() -> None:
    sc = StructureConfig()
    with pytest.raises(AttributeError):
        sc.x = 1  # type: ignore[attr-defined]


def test_signal_config_immutable() -> None:
    sc = SignalConfig()
    with pytest.raises(AttributeError):
        sc.x = 1  # type: ignore[attr-defined]
