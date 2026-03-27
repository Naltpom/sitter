"""TTS engine factory."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .base import TTSEngine

_engines: dict[str, TTSEngine] = {}


def get_engine(name: str) -> TTSEngine:
    """Return a cached engine instance by name."""
    if name not in _engines:
        if name == "piper":
            from .piper_engine import PiperEngine
            _engines[name] = PiperEngine()
        elif name == "xtts":
            from .xtts_engine import XTTSEngine
            _engines[name] = XTTSEngine()
        else:
            raise ValueError(f"Unknown TTS engine: {name}")
    return _engines[name]
