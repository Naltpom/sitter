"""App settings endpoints: public info + admin CRUD + logo upload."""

import os
import shutil
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..events import event_bus
from ..permissions import require_permission
from ..security import get_current_user
from .models import AppSetting
from .schemas import AppSettingResponse, AppSettingsUpdate

router = APIRouter()

# Default settings with their initial values
DEFAULTS: dict[str, str] = {
    "app_name": "Sitter",
    "app_description": "",
    "app_logo": "/logo_full.svg",
    "app_favicon": "/favicon.svg",
    "primary_color": "#1E40AF",
    "support_email": "",
    "header_show_logo": "true",
    "header_show_name": "true",
}

UPLOAD_DIR = "/app/uploads/settings"


async def _get_all_settings(db: AsyncSession) -> dict[str, str | None]:
    """Return all settings as a dict, with defaults for missing keys."""
    result = await db.execute(select(AppSetting))
    rows = {s.key: s.value for s in result.scalars().all()}
    merged = {**DEFAULTS, **rows}
    return merged


# ---------------------------------------------------------------------------
#  Public endpoint (no auth) — used by login page, header, etc.
# ---------------------------------------------------------------------------


@router.get("/public")
async def get_public_settings(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Return app branding info + SSO providers. No authentication required."""
    all_settings = await _get_all_settings(db)

    # SSO providers from feature registry
    registry = request.app.state.feature_registry
    providers = []
    for provider_name, label in [("google", "Google"), ("github", "GitHub")]:
        providers.append({
            "name": provider_name,
            "label": label,
            "enabled": registry.is_active(f"sso.{provider_name}"),
        })

    return {
        "app_name": all_settings.get("app_name"),
        "app_description": all_settings.get("app_description"),
        "app_logo": all_settings.get("app_logo"),
        "app_favicon": all_settings.get("app_favicon"),
        "primary_color": all_settings.get("primary_color"),
        "header_show_logo": all_settings.get("header_show_logo"),
        "header_show_name": all_settings.get("header_show_name"),
        "providers": providers,
    }


# ---------------------------------------------------------------------------
#  Admin: list all settings
# ---------------------------------------------------------------------------


@router.get(
    "/",
    response_model=list[AppSettingResponse],
    dependencies=[Depends(require_permission("settings.read"))],
)
async def list_settings(db: AsyncSession = Depends(get_db)):
    """List all app settings (admin)."""
    result = await db.execute(select(AppSetting).order_by(AppSetting.key))
    stored = {s.key: s for s in result.scalars().all()}

    out: list[AppSettingResponse] = []
    for key in sorted(set(list(DEFAULTS.keys()) + list(stored.keys()))):
        if key in stored:
            s = stored[key]
            out.append(AppSettingResponse(key=s.key, value=s.value, updated_at=s.updated_at))
        else:
            out.append(AppSettingResponse(key=key, value=DEFAULTS.get(key)))
    return out


# ---------------------------------------------------------------------------
#  Admin: bulk update settings
# ---------------------------------------------------------------------------


@router.put(
    "/",
    response_model=list[AppSettingResponse],
    dependencies=[Depends(require_permission("settings.manage"))],
)
async def update_settings(
    data: AppSettingsUpdate,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Bulk update app settings (admin)."""
    now = datetime.now(timezone.utc)

    for key, value in data.settings.items():
        result = await db.execute(select(AppSetting).where(AppSetting.key == key))
        existing = result.scalar_one_or_none()
        if existing:
            existing.value = value
            existing.updated_at = now
            existing.updated_by = current_user.id
        else:
            db.add(AppSetting(key=key, value=value, updated_at=now, updated_by=current_user.id))

    await db.flush()

    await event_bus.emit(
        "admin.settings_updated",
        db=db,
        actor_id=current_user.id,
        resource_type="settings",
        resource_id=0,
        payload={"keys": list(data.settings.keys()), "updated_by": current_user.email},
    )

    # Return all settings after update
    return await list_settings(db=db)


# ---------------------------------------------------------------------------
#  Admin: upload logo
# ---------------------------------------------------------------------------


@router.post(
    "/logo",
    dependencies=[Depends(require_permission("settings.manage"))],
)
async def upload_logo(
    file: UploadFile = File(...),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload a new app logo."""
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Le fichier doit etre une image")

    if file.size and file.size > 2 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Le fichier ne doit pas depasser 2 Mo")

    os.makedirs(UPLOAD_DIR, exist_ok=True)

    ext = os.path.splitext(file.filename or "logo.png")[1] or ".png"
    filename = f"logo_{uuid.uuid4().hex[:8]}{ext}"
    filepath = os.path.join(UPLOAD_DIR, filename)

    with open(filepath, "wb") as f:
        shutil.copyfileobj(file.file, f)

    logo_url = f"/uploads/settings/{filename}"

    # Update setting
    now = datetime.now(timezone.utc)
    result = await db.execute(select(AppSetting).where(AppSetting.key == "app_logo"))
    existing = result.scalar_one_or_none()
    if existing:
        existing.value = logo_url
        existing.updated_at = now
        existing.updated_by = current_user.id
    else:
        db.add(AppSetting(key="app_logo", value=logo_url, updated_at=now, updated_by=current_user.id))

    await db.flush()

    return {"logo_url": logo_url}


# ---------------------------------------------------------------------------
#  Admin: upload favicon
# ---------------------------------------------------------------------------


@router.post(
    "/favicon",
    dependencies=[Depends(require_permission("settings.manage"))],
)
async def upload_favicon(
    file: UploadFile = File(...),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload a new app favicon."""
    allowed_types = ["image/x-icon", "image/vnd.microsoft.icon", "image/png", "image/svg+xml"]
    if not file.content_type or file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Le fichier doit etre un favicon (.ico, .png, .svg)")

    if file.size and file.size > 1 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Le fichier ne doit pas depasser 1 Mo")

    os.makedirs(UPLOAD_DIR, exist_ok=True)

    ext = os.path.splitext(file.filename or "favicon.ico")[1] or ".ico"
    filename = f"favicon_{uuid.uuid4().hex[:8]}{ext}"
    filepath = os.path.join(UPLOAD_DIR, filename)

    with open(filepath, "wb") as f:
        shutil.copyfileobj(file.file, f)

    favicon_url = f"/uploads/settings/{filename}"

    # Update setting
    now = datetime.now(timezone.utc)
    result = await db.execute(select(AppSetting).where(AppSetting.key == "app_favicon"))
    existing = result.scalar_one_or_none()
    if existing:
        existing.value = favicon_url
        existing.updated_at = now
        existing.updated_by = current_user.id
    else:
        db.add(AppSetting(key="app_favicon", value=favicon_url, updated_at=now, updated_by=current_user.id))

    await db.flush()

    return {"favicon_url": favicon_url}


# ---------------------------------------------------------------------------
#  Admin: reset logo / favicon to defaults
# ---------------------------------------------------------------------------


async def _reset_setting(key: str, current_user, db: AsyncSession) -> str:
    """Reset a setting to its default value and return the default."""
    default_value = DEFAULTS[key]
    now = datetime.now(timezone.utc)

    result = await db.execute(select(AppSetting).where(AppSetting.key == key))
    existing = result.scalar_one_or_none()
    if existing:
        existing.value = default_value
        existing.updated_at = now
        existing.updated_by = current_user.id
    else:
        db.add(AppSetting(key=key, value=default_value, updated_at=now, updated_by=current_user.id))

    await db.flush()
    return default_value


@router.delete(
    "/logo",
    dependencies=[Depends(require_permission("settings.manage"))],
)
async def reset_logo(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Reset logo to default."""
    default = await _reset_setting("app_logo", current_user, db)
    return {"logo_url": default}


@router.delete(
    "/favicon",
    dependencies=[Depends(require_permission("settings.manage"))],
)
async def reset_favicon(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Reset favicon to default."""
    default = await _reset_setting("app_favicon", current_user, db)
    return {"favicon_url": default}
