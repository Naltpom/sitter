"""ARQ worker settings for the dedicated TTS worker container."""

import logging

from arq.connections import RedisSettings

from ...core.config import settings
from .tasks import generate_audio_task, preview_voice_task

logger = logging.getLogger(__name__)


def _parse_redis_url(url: str) -> RedisSettings:
    from urllib.parse import urlparse

    parsed = urlparse(url)
    return RedisSettings(
        host=parsed.hostname or "redis",
        port=parsed.port or 6379,
        database=int(parsed.path.lstrip("/") or 0),
        password=parsed.password,
    )


async def _on_startup(ctx):
    # Import User model so SQLAlchemy relationships resolve correctly
    import src.core._identity.models  # noqa: F401
    logger.info("TTS worker started.")


class WorkerSettings:
    functions = [generate_audio_task, preview_voice_task]
    redis_settings = _parse_redis_url(settings.REDIS_URL)
    queue_name = "arq:tts"  # Dedicated queue — isolate from main worker
    max_jobs = 2
    job_timeout = 600  # 10 minutes per job
    on_startup = _on_startup
