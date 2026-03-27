"""Abstract base class for TTS engines."""

from abc import ABC, abstractmethod


class TTSEngine(ABC):

    @abstractmethod
    async def synthesize(self, text: str, voice_config: dict) -> bytes:
        """Generate WAV audio bytes from text using the given voice config.

        Args:
            text: Plain text to synthesize.
            voice_config: Engine-specific config (model_name for piper, reference_audio_path for xtts).

        Returns:
            Raw WAV audio bytes.
        """
        ...

    @abstractmethod
    async def is_available(self) -> bool:
        """Check if this engine and its required models are ready."""
        ...
