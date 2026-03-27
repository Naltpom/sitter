"""Piper TTS engine wrapper for generic voices."""

import asyncio
import io
import logging
import wave
from pathlib import Path

from ....core.config import settings
from .base import TTSEngine

logger = logging.getLogger(__name__)

# Available French Piper voices (model_name -> download info)
PIPER_FRENCH_VOICES = {
    "fr_FR-siwis-medium": {
        "label": "Siwis (Femme)",
        "quality": "medium",
    },
    "fr_FR-upmc-medium": {
        "label": "UPMC (Homme)",
        "quality": "medium",
    },
}


class PiperEngine(TTSEngine):
    """Piper TTS engine for fast, lightweight, CPU-friendly synthesis."""

    def __init__(self):
        self._models_dir = Path(settings.TTS_MODELS_DIR) / "piper"
        self._models_dir.mkdir(parents=True, exist_ok=True)

    def _synthesize_sync(self, text: str, model_name: str) -> bytes:
        """Synchronous synthesis — runs in thread pool."""
        import numpy as np
        from piper import PiperVoice

        model_path = self._models_dir / f"{model_name}.onnx"
        config_path = self._models_dir / f"{model_name}.onnx.json"

        if not model_path.exists():
            self._download_model(model_name)

        voice = PiperVoice.load(str(model_path), config_path=str(config_path))

        # Collect all audio chunks from synthesize iterator
        all_audio = []
        sample_rate = 22050
        for chunk in voice.synthesize(text):
            sample_rate = chunk.sample_rate
            all_audio.append(chunk.audio_float_array)

        if not all_audio:
            raise ValueError("Piper returned no audio chunks")

        combined = np.concatenate(all_audio)
        audio_int16 = (combined * 32767).astype(np.int16)

        # Write WAV
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(audio_int16.tobytes())

        return wav_buffer.getvalue()

    def _download_model(self, model_name: str):
        """Download a Piper model from HuggingFace."""
        import urllib.request

        base_url = "https://huggingface.co/rhasspy/piper-voices/resolve/main"
        lang_code = model_name.split("-")[0]  # fr_FR
        lang_short = lang_code.split("_")[0]  # fr
        voice_name = "-".join(model_name.split("-")[1:-1])  # siwis
        quality = model_name.split("-")[-1]  # medium

        onnx_url = f"{base_url}/{lang_short}/{lang_code}/{voice_name}/{quality}/{model_name}.onnx"
        json_url = f"{onnx_url}.json"

        onnx_path = self._models_dir / f"{model_name}.onnx"
        json_path = self._models_dir / f"{model_name}.onnx.json"

        logger.info("Downloading Piper model %s ...", model_name)
        urllib.request.urlretrieve(onnx_url, str(onnx_path))
        urllib.request.urlretrieve(json_url, str(json_path))
        logger.info("Piper model %s downloaded successfully.", model_name)

    async def synthesize(self, text: str, voice_config: dict) -> bytes:
        """Generate WAV audio from text using Piper TTS."""
        model_name = voice_config.get("model_name", "fr_FR-siwis-medium")
        return await asyncio.to_thread(self._synthesize_sync, text, model_name)

    async def is_available(self) -> bool:
        try:
            import piper  # noqa: F401
            return True
        except ImportError:
            return False
