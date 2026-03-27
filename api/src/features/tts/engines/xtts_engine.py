"""Coqui XTTS v2 engine wrapper for voice cloning."""

import asyncio
import io
import logging
import wave
from pathlib import Path

import numpy as np

from ....core.config import settings
from .base import TTSEngine

logger = logging.getLogger(__name__)


class XTTSEngine(TTSEngine):
    """Coqui XTTS v2 engine for voice cloning from reference audio."""

    def __init__(self):
        self._models_dir = Path(settings.TTS_MODELS_DIR) / "xtts"
        self._models_dir.mkdir(parents=True, exist_ok=True)
        self._tts = None

    def _get_tts(self):
        """Lazy-load the TTS model (heavy, ~2GB)."""
        if self._tts is None:
            import os

            import torch
            from TTS.api import TTS

            # Auto-accept Coqui CPML license (non-interactive container)
            os.environ["COQUI_TOS_AGREED"] = "1"
            # PyTorch 2.6+ defaults to weights_only=True which breaks XTTS checkpoint loading
            torch.serialization.add_safe_globals([])  # noqa
            original_load = torch.load
            torch.load = lambda *args, **kwargs: original_load(*args, **{**kwargs, "weights_only": False})

            logger.info("Loading XTTS v2 model (this may take a moment)...")
            self._tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2")
            # Move to GPU if available
            import torch
            if torch.cuda.is_available():
                self._tts = self._tts.to("cuda")
                logger.info("XTTS v2 loaded on GPU (CUDA).")
            else:
                logger.info("XTTS v2 loaded on CPU.")
        return self._tts

    def _synthesize_sync(self, text: str, reference_audio_path: str, language: str = "fr") -> bytes:
        """Synchronous synthesis with voice cloning — runs in thread pool."""
        tts = self._get_tts()

        # Generate audio using reference speaker
        wav_array = tts.tts(
            text=text,
            speaker_wav=reference_audio_path,
            language=language,
        )

        # Convert numpy array to WAV bytes
        wav_buffer = io.BytesIO()
        sample_rate = tts.synthesizer.output_sample_rate if hasattr(tts, "synthesizer") else 22050

        wav_np = np.array(wav_array, dtype=np.float32)
        # Normalize to int16 range
        wav_int16 = (wav_np * 32767).astype(np.int16)

        with wave.open(wav_buffer, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(wav_int16.tobytes())

        return wav_buffer.getvalue()

    async def synthesize(self, text: str, voice_config: dict) -> bytes:
        """Generate WAV audio from text using XTTS v2 voice cloning."""
        reference_audio_path = voice_config.get("reference_audio_path")
        if not reference_audio_path:
            raise ValueError("reference_audio_path is required for XTTS voice cloning")

        if not Path(reference_audio_path).exists():
            raise FileNotFoundError(f"Reference audio not found: {reference_audio_path}")

        language = voice_config.get("language", "fr")
        return await asyncio.to_thread(self._synthesize_sync, text, reference_audio_path, language)

    async def is_available(self) -> bool:
        try:
            import TTS  # noqa: F401
            return True
        except ImportError:
            return False
