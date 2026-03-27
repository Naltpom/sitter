"""TTS feature business logic."""

from __future__ import annotations

import os
import re
import uuid as uuid_mod
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.config import settings
from .models import AudioGeneration, Conversation, Voice

# -- Voices -------------------------------------------------------------------


async def list_voices(db: AsyncSession, user_id: int) -> list[Voice]:
    """Return all generic voices + the user's custom voices."""
    stmt = (
        select(Voice)
        .where(
            Voice.is_active == True,  # noqa: E712
            (Voice.voice_type == "generic") | (Voice.user_id == user_id),
        )
        .order_by(Voice.voice_type, Voice.name)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_voice_by_uuid(db: AsyncSession, voice_uuid: str) -> Voice | None:
    result = await db.execute(select(Voice).where(Voice.uuid == voice_uuid))
    return result.scalar_one_or_none()


async def get_voice_by_slug(db: AsyncSession, slug: str) -> Voice | None:
    result = await db.execute(select(Voice).where(Voice.slug == slug, Voice.is_active == True))  # noqa: E712
    return result.scalar_one_or_none()


def _slugify(name: str) -> str:
    """Generate a URL-safe slug from a name."""
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "_", slug)
    slug = slug.strip("_")
    return slug or "voice"


async def create_custom_voice(
    db: AsyncSession,
    user_id: int,
    name: str,
    audio_data: bytes,
    audio_filename: str,
    slug: str | None = None,
    color: str = "#6366f1",
    language: str = "fr",
) -> Voice:
    """Create a custom voice from reference audio."""
    # Save reference audio
    ref_dir = Path(settings.TTS_REFERENCE_DIR)
    ref_dir.mkdir(parents=True, exist_ok=True)

    ext = os.path.splitext(audio_filename)[1].lower() or ".wav"
    ref_filename = f"{uuid_mod.uuid4().hex}{ext}"
    ref_path = ref_dir / ref_filename

    with open(ref_path, "wb") as f:
        f.write(audio_data)

    # Generate slug if not provided, ensure uniqueness
    base_slug = _slugify(slug or name)
    final_slug = base_slug
    counter = 1
    while await get_voice_by_slug(db, final_slug):
        final_slug = f"{base_slug}_{counter}"
        counter += 1

    voice = Voice(
        name=name,
        slug=final_slug,
        voice_type="custom",
        engine="xtts",
        reference_audio_path=str(ref_path),
        color=color,
        language=language,
        user_id=user_id,
    )
    db.add(voice)
    await db.flush()
    return voice


async def update_voice(
    db: AsyncSession,
    voice_uuid: str,
    user_id: int,
    name: str | None = None,
    color: str | None = None,
    audio_data: bytes | None = None,
    audio_filename: str | None = None,
) -> Voice | None:
    """Update a custom voice (only owner can update)."""
    voice = await get_voice_by_uuid(db, voice_uuid)
    if not voice or voice.voice_type != "custom" or voice.user_id != user_id:
        return None

    if name is not None:
        voice.name = name
    if color is not None:
        voice.color = color

    # Replace reference audio if provided
    if audio_data:
        ref_dir = Path(settings.TTS_REFERENCE_DIR)
        ref_dir.mkdir(parents=True, exist_ok=True)

        # Remove old file
        if voice.reference_audio_path and os.path.exists(voice.reference_audio_path):
            os.remove(voice.reference_audio_path)

        ext = os.path.splitext(audio_filename or "audio.wav")[1].lower() or ".wav"
        ref_filename = f"{uuid_mod.uuid4().hex}{ext}"
        ref_path = ref_dir / ref_filename

        with open(ref_path, "wb") as f:
            f.write(audio_data)

        voice.reference_audio_path = str(ref_path)

    await db.flush()
    return voice


async def delete_voice(db: AsyncSession, voice_uuid: str, user_id: int) -> bool:
    """Delete a custom voice (only owner can delete)."""
    voice = await get_voice_by_uuid(db, voice_uuid)
    if not voice or voice.voice_type != "custom" or voice.user_id != user_id:
        return False

    # Remove reference audio file
    if voice.reference_audio_path and os.path.exists(voice.reference_audio_path):
        os.remove(voice.reference_audio_path)

    await db.delete(voice)
    return True


# -- Conversations ------------------------------------------------------------


async def list_conversations(
    db: AsyncSession,
    user_id: int,
    page: int = 1,
    per_page: int = 20,
) -> tuple[list[Conversation], int]:
    """Return paginated list of user's conversations."""
    count_stmt = select(Conversation).where(Conversation.user_id == user_id)
    result = await db.execute(count_stmt)
    all_items = list(result.scalars().all())
    total = len(all_items)

    stmt = (
        select(Conversation)
        .where(Conversation.user_id == user_id)
        .order_by(desc(Conversation.updated_at))
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    result = await db.execute(stmt)
    items = list(result.scalars().all())
    return items, total


async def get_conversation_by_uuid(db: AsyncSession, conv_uuid: str) -> Conversation | None:
    result = await db.execute(select(Conversation).where(Conversation.uuid == conv_uuid))
    return result.scalar_one_or_none()


async def create_conversation(
    db: AsyncSession,
    user_id: int,
    title: str,
    content: str,
) -> Conversation:
    if len(content) > settings.TTS_MAX_TEXT_LENGTH:
        raise ValueError(f"Le contenu depasse la limite de {settings.TTS_MAX_TEXT_LENGTH} caracteres")

    conv = Conversation(title=title, content=content, user_id=user_id)
    db.add(conv)
    await db.flush()
    return conv


async def update_conversation(
    db: AsyncSession,
    conv_uuid: str,
    user_id: int,
    title: str | None = None,
    content: str | None = None,
) -> Conversation | None:
    conv = await get_conversation_by_uuid(db, conv_uuid)
    if not conv or conv.user_id != user_id:
        return None

    if title is not None:
        conv.title = title
    if content is not None:
        if len(content) > settings.TTS_MAX_TEXT_LENGTH:
            raise ValueError(f"Le contenu depasse la limite de {settings.TTS_MAX_TEXT_LENGTH} caracteres")
        conv.content = content

    conv.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return conv


async def delete_conversation(db: AsyncSession, conv_uuid: str, user_id: int) -> bool:
    conv = await get_conversation_by_uuid(db, conv_uuid)
    if not conv or conv.user_id != user_id:
        return False
    await db.delete(conv)
    return True


# -- Generations --------------------------------------------------------------


async def get_generation_by_uuid(db: AsyncSession, gen_uuid: str) -> AudioGeneration | None:
    result = await db.execute(select(AudioGeneration).where(AudioGeneration.uuid == gen_uuid))
    return result.scalar_one_or_none()


async def get_latest_generation(db: AsyncSession, conversation_id: int) -> AudioGeneration | None:
    stmt = (
        select(AudioGeneration)
        .where(AudioGeneration.conversation_id == conversation_id)
        .order_by(desc(AudioGeneration.created_at))
        .limit(1)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def start_generation(
    db: AsyncSession,
    conversation_id: int,
    user_id: int,
) -> AudioGeneration:
    """Create a new audio generation record (pending). Caller enqueues ARQ task."""
    gen = AudioGeneration(
        conversation_id=conversation_id,
        user_id=user_id,
        status="pending",
    )
    db.add(gen)
    await db.flush()
    return gen
