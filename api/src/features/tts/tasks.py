"""TTS background tasks for ARQ worker."""

import base64
import logging
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from ...core.config import settings

logger = logging.getLogger(__name__)


async def preview_voice_task(ctx, engine_name: str, voice_config: dict, text: str) -> str:
    """Generate a short audio preview and return WAV bytes as base64.

    Runs in tts-worker which has TTS libs installed.
    Returns base64 string so ARQ can serialize the result via Redis.
    """
    from .engines import get_engine

    engine = get_engine(engine_name)
    wav_data = await engine.synthesize(text, voice_config)
    return base64.b64encode(wav_data).decode("ascii")


async def _push_progress(user_id: int, generation_uuid: str, data: dict):
    """Push SSE progress event to the user."""
    try:
        from ...core.realtime.services import sse_broadcaster
        await sse_broadcaster.push(
            user_id,
            event_type="tts_progress",
            data={"generation_uuid": generation_uuid, **data},
        )
    except Exception as e:
        logger.debug("SSE push failed (non-critical): %s", e)


async def generate_audio_task(ctx, generation_id: int) -> dict:
    """Generate audio from a conversation's content.

    This task runs in the tts-worker container which has TTS dependencies installed.
    Progress is pushed to the user via SSE (Redis pub/sub).
    """
    from ...core.database import async_session
    from .audio import concatenate_segments, get_audio_duration, wav_to_mp3
    from .engines import get_engine
    from .models import AudioGeneration, Conversation, Voice
    from .parser import parse_content

    async with async_session() as db:
        # Load generation record
        gen = (await db.execute(
            select(AudioGeneration).where(AudioGeneration.id == generation_id)
        )).scalar_one_or_none()

        if not gen:
            logger.error("Generation %d not found", generation_id)
            return {"error": "not found"}

        user_id = gen.user_id

        # Load conversation
        conv = (await db.execute(
            select(Conversation).where(Conversation.id == gen.conversation_id)
        )).scalar_one_or_none()

        if not conv:
            gen.status = "error"
            gen.error_message = "Conversation introuvable"
            await db.commit()
            await _push_progress(user_id, gen.uuid, {"status": "error", "error": "Conversation introuvable"})
            return {"error": "conversation not found"}

        try:
            # Mark as processing
            gen.status = "processing"
            await db.commit()
            await _push_progress(user_id, gen.uuid, {"status": "processing", "progress": 0})

            # Parse content into voice segments
            segments = parse_content(conv.content)
            if not segments:
                gen.status = "error"
                gen.error_message = "Aucun texte a synthetiser"
                await db.commit()
                await _push_progress(user_id, gen.uuid, {"status": "error", "error": "Aucun texte a synthetiser"})
                return {"error": "no segments"}

            gen.total_segments = len(segments)
            await db.commit()
            await _push_progress(user_id, gen.uuid, {
                "status": "processing", "progress": 0,
                "current_segment": 0, "total_segments": len(segments),
            })

            # Build a slug->Voice lookup
            voice_slugs = {s.voice_slug for s in segments}
            voices = {}
            for slug in voice_slugs:
                voice = (await db.execute(
                    select(Voice).where(Voice.slug == slug, Voice.is_active == True)  # noqa: E712
                )).scalar_one_or_none()
                if voice:
                    voices[slug] = voice

            # Synthesize each segment
            wav_segments = []
            for i, segment in enumerate(segments):
                voice = voices.get(segment.voice_slug)
                if not voice:
                    # Fallback to default voice
                    voice = (await db.execute(
                        select(Voice).where(Voice.slug == settings.TTS_DEFAULT_VOICE_SLUG)
                    )).scalar_one_or_none()

                if not voice:
                    logger.warning("No voice found for slug '%s', skipping segment", segment.voice_slug)
                    continue

                # Build engine config
                engine = get_engine(voice.engine)
                voice_config = {}
                if voice.engine == "piper":
                    voice_config["model_name"] = voice.piper_model_name or "fr_FR-siwis-medium"
                elif voice.engine == "xtts":
                    voice_config["reference_audio_path"] = voice.reference_audio_path
                    voice_config["language"] = voice.language

                logger.info("Synthesizing segment %d/%d (voice: %s, engine: %s)",
                            i + 1, len(segments), voice.slug, voice.engine)

                wav_data = await engine.synthesize(segment.text, voice_config)
                wav_segments.append(wav_data)

                # Update progress in DB + SSE
                progress = int(((i + 1) / len(segments)) * 100)
                gen.current_segment = i + 1
                gen.progress = progress
                await db.commit()
                await _push_progress(user_id, gen.uuid, {
                    "status": "processing", "progress": progress,
                    "current_segment": i + 1, "total_segments": len(segments),
                })

            if not wav_segments:
                gen.status = "error"
                gen.error_message = "Aucun segment audio genere"
                await db.commit()
                await _push_progress(user_id, gen.uuid, {"status": "error", "error": "Aucun segment audio genere"})
                return {"error": "no audio generated"}

            # Concatenate and convert
            logger.info("Concatenating %d segments...", len(wav_segments))
            combined_wav = concatenate_segments(wav_segments)
            mp3_data = wav_to_mp3(combined_wav)

            # Save output
            output_dir = Path(settings.TTS_OUTPUT_DIR)
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / f"{gen.uuid}.mp3"

            with open(output_path, "wb") as f:
                f.write(mp3_data)

            duration = get_audio_duration(mp3_data, fmt="mp3")

            # Finalize
            gen.status = "done"
            gen.progress = 100
            gen.output_path = str(output_path)
            gen.duration_seconds = duration
            gen.file_size_bytes = len(mp3_data)
            gen.completed_at = datetime.now(timezone.utc)
            await db.commit()

            await _push_progress(user_id, gen.uuid, {
                "status": "done", "progress": 100,
                "current_segment": len(segments), "total_segments": len(segments),
                "duration_seconds": duration, "file_size_bytes": len(mp3_data),
            })

            logger.info("Generation %s complete: %.1fs, %d bytes",
                        gen.uuid, duration, len(mp3_data))
            return {"status": "done", "duration": duration}

        except Exception as e:
            logger.exception("Generation %d failed", generation_id)
            gen.status = "error"
            gen.error_message = str(e)[:500]
            await db.commit()
            await _push_progress(user_id, gen.uuid, {"status": "error", "error": str(e)[:200]})
            return {"error": str(e)}
