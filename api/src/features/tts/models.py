"""TTS feature models."""

import uuid as uuid_mod
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ...core.database import Base


class Voice(Base):
    __tablename__ = "tts_voices"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    uuid: Mapped[str] = mapped_column(
        String(36), unique=True, nullable=False, index=True,
        default=lambda: str(uuid_mod.uuid4()),
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    voice_type: Mapped[str] = mapped_column(String(20), nullable=False, default="generic")
    engine: Mapped[str] = mapped_column(String(20), nullable=False, default="piper")
    piper_model_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reference_audio_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    color: Mapped[str] = mapped_column(String(7), nullable=False, default="#6366f1")
    language: Mapped[str] = mapped_column(String(10), nullable=False, default="fr")
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
    )

    owner = relationship("User", foreign_keys=[user_id])

    __table_args__ = (
        Index("ix_tts_voices_type_active", "voice_type", "is_active"),
    )


class Conversation(Base):
    __tablename__ = "tts_conversations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    uuid: Mapped[str] = mapped_column(
        String(36), unique=True, nullable=False, index=True,
        default=lambda: str(uuid_mod.uuid4()),
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    owner = relationship("User", foreign_keys=[user_id])
    generations = relationship("AudioGeneration", back_populates="conversation", cascade="all, delete-orphan")


class AudioGeneration(Base):
    __tablename__ = "tts_audio_generations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    uuid: Mapped[str] = mapped_column(
        String(36), unique=True, nullable=False, index=True,
        default=lambda: str(uuid_mod.uuid4()),
    )

    conversation_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tts_conversations.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    current_segment: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_segments: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    output_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    output_format: Mapped[str] = mapped_column(String(10), nullable=False, default="mp3")
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    conversation = relationship("Conversation", back_populates="generations")
    owner = relationship("User", foreign_keys=[user_id])

    __table_args__ = (
        Index("ix_tts_generations_status", "status"),
        Index("ix_tts_generations_user_created", "user_id", "created_at"),
    )
