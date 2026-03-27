"""TTS feature Pydantic schemas."""

from datetime import datetime

from pydantic import BaseModel, Field

# -- Voice --------------------------------------------------------------------

class VoiceResponse(BaseModel):
    id: int
    uuid: str
    name: str
    slug: str
    voice_type: str
    engine: str
    piper_model_name: str | None = None
    color: str
    language: str
    is_active: bool
    user_id: int | None = None
    created_at: datetime


class VoiceCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    slug: str | None = Field(None, max_length=100)
    color: str = Field("#6366f1", pattern=r"^#[0-9a-fA-F]{6}$")
    language: str = Field("fr", max_length=10)


class VoicePreviewRequest(BaseModel):
    text: str = Field("Bonjour, ceci est un test de synthese vocale.", max_length=500)


# -- Conversation -------------------------------------------------------------

class ConversationResponse(BaseModel):
    id: int
    uuid: str
    title: str
    content: str
    user_id: int
    created_at: datetime
    updated_at: datetime
    latest_generation: "AudioGenerationResponse | None" = None


class ConversationCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    content: str = Field(..., min_length=1)


class ConversationUpdateRequest(BaseModel):
    title: str | None = Field(None, max_length=255)
    content: str | None = None


# -- Audio Generation ---------------------------------------------------------

class AudioGenerationResponse(BaseModel):
    id: int
    uuid: str
    conversation_id: int
    status: str
    progress: int
    current_segment: int
    total_segments: int
    output_format: str
    duration_seconds: float | None = None
    file_size_bytes: int | None = None
    error_message: str | None = None
    created_at: datetime
    completed_at: datetime | None = None


class GenerationStatusResponse(BaseModel):
    uuid: str
    status: str
    progress: int
    current_segment: int
    total_segments: int
    duration_seconds: float | None = None
    file_size_bytes: int | None = None
    error_message: str | None = None
