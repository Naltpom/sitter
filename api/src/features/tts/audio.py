"""Audio utilities for segment concatenation and format conversion."""

from __future__ import annotations

import io
import logging

from ...core.config import settings

logger = logging.getLogger(__name__)


def concatenate_segments(wav_segments: list[bytes], crossfade_ms: int | None = None) -> bytes:
    """Concatenate multiple WAV audio segments into one with optional crossfade.

    Args:
        wav_segments: List of raw WAV bytes.
        crossfade_ms: Crossfade duration in ms (default from settings).

    Returns:
        Combined WAV bytes.
    """
    from pydub import AudioSegment

    if crossfade_ms is None:
        crossfade_ms = settings.TTS_CROSSFADE_MS

    if not wav_segments:
        raise ValueError("No audio segments to concatenate")

    combined = AudioSegment.from_wav(io.BytesIO(wav_segments[0]))

    for wav_data in wav_segments[1:]:
        segment = AudioSegment.from_wav(io.BytesIO(wav_data))
        if crossfade_ms > 0 and len(combined) > crossfade_ms and len(segment) > crossfade_ms:
            combined = combined.append(segment, crossfade=crossfade_ms)
        else:
            combined = combined + segment

    buf = io.BytesIO()
    combined.export(buf, format="wav")
    return buf.getvalue()


def wav_to_mp3(wav_data: bytes, bitrate: str = "192k") -> bytes:
    """Convert WAV bytes to MP3 bytes.

    Args:
        wav_data: Raw WAV audio bytes.
        bitrate: MP3 bitrate (default "192k").

    Returns:
        MP3 audio bytes.
    """
    from pydub import AudioSegment

    audio = AudioSegment.from_wav(io.BytesIO(wav_data))
    buf = io.BytesIO()
    audio.export(buf, format="mp3", bitrate=bitrate)
    return buf.getvalue()


def get_audio_duration(data: bytes, fmt: str = "wav") -> float:
    """Get audio duration in seconds.

    Args:
        data: Audio bytes.
        fmt: Audio format ("wav" or "mp3").

    Returns:
        Duration in seconds.
    """
    from pydub import AudioSegment

    audio = AudioSegment.from_file(io.BytesIO(data), format=fmt)
    return audio.duration_seconds
