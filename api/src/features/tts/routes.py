"""TTS feature API routes."""

import math
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.database import get_db
from ...core.pagination import PaginatedResponse
from ...core.permissions import require_permission
from ...core.security import get_current_user
from ...core.tasks import get_arq_pool
from .schemas import (
    AudioGenerationResponse,
    ConversationCreateRequest,
    ConversationResponse,
    ConversationUpdateRequest,
    GenerationStatusResponse,
    VoicePreviewRequest,
    VoiceResponse,
)
from .services import (
    create_conversation,
    create_custom_voice,
    delete_conversation,
    delete_voice,
    get_conversation_by_uuid,
    get_generation_by_uuid,
    get_latest_generation,
    get_voice_by_uuid,
    list_conversations,
    list_voices,
    start_generation,
    update_conversation,
)

router = APIRouter()


# -- Helpers ------------------------------------------------------------------

def _voice_response(v) -> VoiceResponse:
    return VoiceResponse(
        id=v.id, uuid=v.uuid, name=v.name, slug=v.slug,
        voice_type=v.voice_type, engine=v.engine,
        piper_model_name=v.piper_model_name, color=v.color,
        language=v.language, is_active=v.is_active,
        user_id=v.user_id, created_at=v.created_at,
    )


def _conv_response(c, gen=None) -> ConversationResponse:
    latest = None
    if gen:
        latest = _gen_response(gen)
    return ConversationResponse(
        id=c.id, uuid=c.uuid, title=c.title, content=c.content,
        user_id=c.user_id, created_at=c.created_at, updated_at=c.updated_at,
        latest_generation=latest,
    )


def _gen_response(g) -> AudioGenerationResponse:
    return AudioGenerationResponse(
        id=g.id, uuid=g.uuid, conversation_id=g.conversation_id,
        status=g.status, progress=g.progress,
        current_segment=g.current_segment, total_segments=g.total_segments,
        output_format=g.output_format, duration_seconds=g.duration_seconds,
        file_size_bytes=g.file_size_bytes, error_message=g.error_message,
        created_at=g.created_at, completed_at=g.completed_at,
    )


# -- Voices -------------------------------------------------------------------


@router.get(
    "/voices",
    response_model=list[VoiceResponse],
    dependencies=[Depends(require_permission("tts.read"))],
)
async def api_list_voices(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    voices = await list_voices(db, current_user.id)
    return [_voice_response(v) for v in voices]


@router.post(
    "/voices",
    response_model=VoiceResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("tts.manage_voices"))],
)
async def api_create_voice(
    file: UploadFile = File(...),
    name: Annotated[str, Form()] = ...,
    slug: Annotated[str | None, Form()] = None,
    color: Annotated[str, Form()] = "#6366f1",
    language: Annotated[str, Form()] = "fr",
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a custom voice from a reference audio upload."""
    audio_data = await file.read()
    if not audio_data:
        raise HTTPException(status_code=400, detail="Fichier audio vide")

    max_bytes = 20 * 1024 * 1024  # 20 MB
    if len(audio_data) > max_bytes:
        raise HTTPException(status_code=413, detail="Fichier audio trop volumineux (max 20 Mo)")

    # Validate audio type
    allowed_types = {"audio/wav", "audio/mpeg", "audio/ogg", "audio/webm", "audio/x-wav", "audio/wave"}
    if file.content_type and file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Type de fichier non supporte (WAV, MP3, OGG, WebM)")

    voice = await create_custom_voice(
        db, current_user.id, name, audio_data, file.filename or "audio.wav",
        slug=slug, color=color, language=language,
    )
    return _voice_response(voice)


@router.put(
    "/voices/{voice_uuid}",
    response_model=VoiceResponse,
    dependencies=[Depends(require_permission("tts.manage_voices"))],
)
async def api_update_voice(
    voice_uuid: str,
    file: UploadFile | None = File(None),
    name: Annotated[str | None, Form()] = None,
    color: Annotated[str | None, Form()] = None,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a custom voice (name, color, reference audio)."""
    from .services import update_voice
    voice = await update_voice(
        db, voice_uuid, current_user.id,
        name=name, color=color,
        audio_data=await file.read() if file else None,
        audio_filename=file.filename if file else None,
    )
    if not voice:
        raise HTTPException(status_code=404, detail="Voix introuvable ou non modifiable")
    return _voice_response(voice)


@router.delete(
    "/voices/{voice_uuid}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permission("tts.manage_voices"))],
)
async def api_delete_voice(
    voice_uuid: str,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    deleted = await delete_voice(db, voice_uuid, current_user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Voix introuvable ou non supprimable")


@router.post(
    "/voices/{voice_uuid}/preview",
    dependencies=[Depends(require_permission("tts.read"))],
)
async def api_preview_voice(
    voice_uuid: str,
    body: VoicePreviewRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate a short audio preview for a voice (delegated to tts-worker)."""
    import base64

    voice = await get_voice_by_uuid(db, voice_uuid)
    if not voice:
        raise HTTPException(status_code=404, detail="Voix introuvable")

    voice_config: dict = {}
    if voice.engine == "piper":
        voice_config["model_name"] = voice.piper_model_name or "fr_FR-siwis-medium"
    elif voice.engine == "xtts":
        voice_config["reference_audio_path"] = voice.reference_audio_path
        voice_config["language"] = voice.language

    # Enqueue preview job on tts-worker (dedicated queue) and wait for result
    pool = await get_arq_pool()
    job = await pool.enqueue_job("preview_voice_task", voice.engine, voice_config, body.text, _queue_name="arq:tts")
    if not job:
        raise HTTPException(status_code=503, detail="Impossible de lancer la preview")

    result = await job.result(timeout=120)
    if not result or not isinstance(result, str):
        raise HTTPException(status_code=500, detail="Erreur lors de la generation de la preview")

    wav_data = base64.b64decode(result)
    return Response(content=wav_data, media_type="audio/wav")


# -- Conversations ------------------------------------------------------------


@router.get(
    "/conversations",
    response_model=PaginatedResponse[ConversationResponse],
    dependencies=[Depends(require_permission("tts.read"))],
)
async def api_list_conversations(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    items, total = await list_conversations(db, current_user.id, page, per_page)
    results = []
    for c in items:
        gen = await get_latest_generation(db, c.id)
        results.append(_conv_response(c, gen))

    return PaginatedResponse(
        items=results, total=total, page=page, per_page=per_page,
        pages=math.ceil(total / per_page) if total > 0 else 0,
    )


@router.post(
    "/conversations",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("tts.create"))],
)
async def api_create_conversation(
    body: ConversationCreateRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        conv = await create_conversation(db, current_user.id, body.title, body.content)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _conv_response(conv)


@router.put(
    "/conversations/{conv_uuid}",
    response_model=ConversationResponse,
    dependencies=[Depends(require_permission("tts.create"))],
)
async def api_update_conversation(
    conv_uuid: str,
    body: ConversationUpdateRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        conv = await update_conversation(db, conv_uuid, current_user.id, body.title, body.content)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation introuvable")
    gen = await get_latest_generation(db, conv.id)
    return _conv_response(conv, gen)


@router.delete(
    "/conversations/{conv_uuid}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permission("tts.create"))],
)
async def api_delete_conversation(
    conv_uuid: str,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    deleted = await delete_conversation(db, conv_uuid, current_user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation introuvable")


# -- Generation ---------------------------------------------------------------


@router.post(
    "/conversations/{conv_uuid}/generate",
    response_model=AudioGenerationResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("tts.create"))],
)
async def api_trigger_generation(
    conv_uuid: str,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Trigger audio generation for a conversation."""
    conv = await get_conversation_by_uuid(db, conv_uuid)
    if not conv or conv.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Conversation introuvable")

    gen = await start_generation(db, conv.id, current_user.id)
    await db.commit()

    # Enqueue background task on dedicated tts-worker queue
    pool = await get_arq_pool()
    await pool.enqueue_job("generate_audio_task", gen.id, _queue_name="arq:tts")

    return _gen_response(gen)


@router.get(
    "/generations/{gen_uuid}/status",
    response_model=GenerationStatusResponse,
    dependencies=[Depends(require_permission("tts.read"))],
)
async def api_generation_status(
    gen_uuid: str,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    gen = await get_generation_by_uuid(db, gen_uuid)
    if not gen or gen.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Generation introuvable")

    return GenerationStatusResponse(
        uuid=gen.uuid, status=gen.status, progress=gen.progress,
        current_segment=gen.current_segment, total_segments=gen.total_segments,
        duration_seconds=gen.duration_seconds, file_size_bytes=gen.file_size_bytes,
        error_message=gen.error_message,
    )


@router.get(
    "/generations/{gen_uuid}/download",
    dependencies=[Depends(require_permission("tts.read"))],
)
async def api_download_audio(
    gen_uuid: str,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    gen = await get_generation_by_uuid(db, gen_uuid)
    if not gen or gen.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Generation introuvable")
    if gen.status != "done" or not gen.output_path:
        raise HTTPException(status_code=400, detail="Audio non disponible")

    return FileResponse(
        gen.output_path,
        media_type="audio/mpeg",
        filename=f"tts_{gen.uuid}.mp3",
    )
