"""Auth endpoints: login, refresh, me, preferences, change-password,
forgot-password, reset-password, register, verify-email."""

import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import (
    APIRouter,
    Body,
    Depends,
    File,
    HTTPException,
    Request,
    Response,
    UploadFile,
    status,
)
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..database import get_db
from ..events import event_bus
from ..permissions import get_user_permission_codes, require_permission
from ..rate_limit import limiter, login_limiter
from ..security import (
    clear_refresh_cookie,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
    hash_password,
    hash_refresh_token,
    set_refresh_cookie,
    validate_password,
    verify_password,
)
from .models import User, UserSession
from .schemas import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    ProfileUpdate,
    RegisterRequest,
    RegisterResponse,
    ResendVerificationRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserResponse,
    VerifyEmailRequest,
    VerifyTokenRequest,
)
from .services import (
    authenticate_user,
    consume_security_token,
    create_security_token,
    get_latest_security_token,
    verify_security_token,
)

router = APIRouter()


async def _create_session(
    db: AsyncSession,
    user_id: int,
    refresh_token: str,
    req: Request | None = None,
) -> None:
    """Create a user session record for refresh token tracking."""
    session = UserSession(
        user_id=user_id,
        refresh_token_hash=hash_refresh_token(refresh_token),
        ip_address=req.client.host if req and req.client else None,
        user_agent=(req.headers.get("user-agent", "")[:500]) if req else None,
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    db.add(session)


# ---------------------------------------------------------------------------
#  Login / Refresh
# ---------------------------------------------------------------------------


@router.post("/login", response_model=TokenResponse)
@limiter.limit(settings.RATE_LIMIT_LOGIN)
async def login(data: LoginRequest, request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    ip = request.client.host if request.client else "unknown"
    data.email = data.email.lower()

    # -- Brute-force rate limit check (email + IP tracking) -------------
    allowed, retry_after = login_limiter.check(data.email, ip)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Trop de tentatives. Réessayez dans {retry_after} secondes.",
            headers={"Retry-After": str(retry_after)},
        )

    try:
        result = await authenticate_user(db, data.email, data.password)
    except HTTPException:
        login_limiter.record_failure(data.email, ip)
        raise

    login_limiter.record_success(data.email)

    # Set refresh token as HttpOnly cookie + create session
    refresh = result.pop("refresh_token", "")
    if refresh:
        set_refresh_cookie(response, refresh)
        token_payload = decode_token(result["access_token"])
        user_id = int(token_payload.get("sub", 0))
        if user_id:
            await _create_session(db, user_id, refresh, request)
            await db.flush()

            await event_bus.emit(
                "user.login",
                db=db,
                actor_id=user_id,
                resource_type="user",
                resource_id=user_id,
                payload={"email": data.email, "ip": ip},
            )
    return TokenResponse(**result)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    req: Request, response: Response, db: AsyncSession = Depends(get_db),
):
    # Read refresh token from HttpOnly cookie
    cookie_token = req.cookies.get("refresh_token")
    if not cookie_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de rafraichissement manquant",
        )

    payload = decode_token(cookie_token)
    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de rafraichissement invalide",
        )
    user_id = int(payload.get("sub", 0))

    # Look up session by token hash (FOR UPDATE prevents concurrent reuse)
    old_hash = hash_refresh_token(cookie_token)
    sess_result = await db.execute(
        select(UserSession)
        .where(UserSession.refresh_token_hash == old_hash)
        .with_for_update()
    )
    old_session = sess_result.scalar_one_or_none()

    if old_session:
        if old_session.is_revoked:
            # Token reuse detected — revoke ALL sessions for this user
            await db.execute(
                update(UserSession)
                .where(UserSession.user_id == old_session.user_id, UserSession.is_revoked.is_(False))
                .values(is_revoked=True)
            )
            await db.flush()
            clear_refresh_cookie(response)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token reutilise — toutes les sessions ont ete revoquees",
            )
        # Revoke the old session
        old_session.is_revoked = True

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active or not user.can_login or user.deleted_at is not None or user.archived_at is not None:
        clear_refresh_cookie(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Utilisateur introuvable",
        )

    token_data = {"sub": str(user.id), "email": user.email, "lang": user.language}

    # Preserve impersonation claims through token refresh
    if payload.get("impersonated_by"):
        token_data["impersonated_by"] = payload["impersonated_by"]
        token_data["impersonation_session_id"] = payload.get("impersonation_session_id")

    new_refresh = create_refresh_token(token_data)

    # Create new session + set new cookie
    await _create_session(db, user.id, new_refresh, req)
    await db.flush()
    set_refresh_cookie(response, new_refresh)

    return TokenResponse(
        access_token=create_access_token(token_data),
    )


# ---------------------------------------------------------------------------
#  Current user
# ---------------------------------------------------------------------------


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user=Depends(get_current_user),
    permission_codes: list[str] = Depends(get_user_permission_codes),
    db: AsyncSession = Depends(get_db),
):
    from ..rgpd.routes_politique import get_pending_acceptances_for_user

    pending, has_previous = await get_pending_acceptances_for_user(
        db, current_user.id, user_created_at=current_user.created_at,
    )

    # Check MFA policy requirement (dynamic import, only if feature active)
    mfa_setup_required = False
    mfa_grace_period_expires = None
    try:
        from ..feature_registry import get_registry
        registry = get_registry()
        if registry and registry.is_active("mfa"):
            from ..mfa.services import is_mfa_required_for_user
            mfa_result = await is_mfa_required_for_user(db, current_user)
            mfa_setup_required = mfa_result.get("mfa_setup_required", False)
            if mfa_setup_required:
                from datetime import timedelta
                grace_days = mfa_result.get("grace_period_days", 7)
                policy_updated = mfa_result.get("policy_updated_at")
                if policy_updated:
                    from datetime import datetime as _dt
                    policy_dt = _dt.fromisoformat(policy_updated)
                    start = max(policy_dt, current_user.created_at)
                else:
                    start = current_user.created_at
                expires = start + timedelta(days=grace_days)
                mfa_grace_period_expires = expires.isoformat()
    except Exception:
        pass  # MFA feature not active

    # Resolve avatar URL
    avatar_url = None
    if getattr(current_user, "avatar_file_id", None):
        from ..file_storage.models import StorageDocument
        avatar_doc = await db.scalar(
            select(StorageDocument).where(StorageDocument.id == current_user.avatar_file_id)
        )
        if avatar_doc:
            avatar_url = f"/api/file-storage/files/{avatar_doc.uuid}/thumbnail"

    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        first_name=current_user.first_name,
        last_name=current_user.last_name,
        auth_source=current_user.auth_source,
        is_active=current_user.is_active,
        can_login=current_user.can_login,
        must_change_password=current_user.must_change_password,
        preferences=current_user.preferences,
        last_login=current_user.last_login,
        last_active=current_user.last_active,
        created_at=current_user.created_at,
        avatar_url=avatar_url,
        pending_legal_acceptances=pending,
        has_previous_acceptances=has_previous,
        mfa_setup_required=mfa_setup_required,
        mfa_grace_period_expires=mfa_grace_period_expires,
    )


@router.get("/me/permissions")
async def get_my_permissions(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the current user's permissions with scope information.

    Returns a dict where each key is a permission code and the value
    contains is_global (bool) and scopes (dict of scope_type -> list of scope_ids).
    """
    from ..permissions import load_user_scoped_permissions

    grants = await load_user_scoped_permissions(db, current_user.id)
    return {
        "permissions": {
            code: {
                "is_global": grant.is_global,
                "scopes": grant.scopes,
            }
            for code, grant in grants.items()
            if grant.granted
        }
    }


@router.get("/me/memberships")
async def get_my_memberships(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the current user's scoped role memberships in a generic format.

    Returns raw scope_type/scope_id pairs without resolving entity names.
    This keeps the endpoint feature-agnostic. The frontend can resolve
    entity details via the relevant feature APIs.

    Requires the UserRole model to have scope_type and scope_id columns.
    Returns empty dict if scoped roles are not enabled.
    """
    from .models import UserRole

    # Check if the UserRole model has scope columns (they may not exist yet)
    if not hasattr(UserRole, "scope_type") or not hasattr(UserRole, "scope_id"):
        return {}

    result = await db.execute(
        select(UserRole.scope_type, UserRole.scope_id).distinct()
        .where(
            UserRole.user_id == current_user.id,
            UserRole.scope_type.isnot(None),
            UserRole.scope_type != "global",
            UserRole.scope_id.isnot(None),
            UserRole.scope_id != 0,
        )
    )

    memberships: dict[str, list[int]] = {}
    for scope_type, scope_id in result.all():
        if scope_type not in memberships:
            memberships[scope_type] = []
        memberships[scope_type].append(scope_id)

    return memberships


@router.put("/me", response_model=UserResponse)
async def update_me(
    data: ProfileUpdate,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == current_user.id))
    user = result.scalar_one()

    if data.email is not None and data.email.lower() != user.email:
        new_email = data.email.lower()
        existing = await db.execute(select(User).where(User.email == new_email))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cet email est deja utilise")
        user.email = new_email
        # Sync MFA email address if mfa feature is active
        try:
            from ..mfa.models import UserMFA
            mfa_result = await db.execute(
                select(UserMFA).where(UserMFA.user_id == user.id, UserMFA.method == "email")
            )
            mfa_email_record = mfa_result.scalar_one_or_none()
            if mfa_email_record:
                mfa_email_record.email_address = new_email
        except Exception:
            pass  # MFA feature not active
    if data.first_name is not None:
        user.first_name = data.first_name
    if data.last_name is not None:
        user.last_name = data.last_name

    await db.flush()

    from ..rgpd.routes_politique import get_pending_acceptances_for_user
    pending, has_previous = await get_pending_acceptances_for_user(
        db, user.id, user_created_at=user.created_at,
    )
    # Resolve avatar URL
    avatar_url = None
    if getattr(user, "avatar_file_id", None):
        from ..file_storage.models import StorageDocument
        avatar_doc = await db.scalar(
            select(StorageDocument).where(StorageDocument.id == user.avatar_file_id)
        )
        if avatar_doc:
            avatar_url = f"/api/file-storage/files/{avatar_doc.uuid}/thumbnail"

    return UserResponse(
        id=user.id,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        auth_source=user.auth_source,
        is_active=user.is_active,
        can_login=user.can_login,
        must_change_password=user.must_change_password,
        preferences=user.preferences,
        last_login=user.last_login,
        last_active=user.last_active,
        created_at=user.created_at,
        avatar_url=avatar_url,
        pending_legal_acceptances=pending,
        has_previous_acceptances=has_previous,
    )


# ---------------------------------------------------------------------------
#  Avatar
# ---------------------------------------------------------------------------


@router.put(
    "/me/avatar",
    dependencies=[Depends(require_permission("file_storage.upload"))],
)
async def upload_avatar(
    file: UploadFile = File(...),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload or replace the current user's avatar."""
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Le fichier doit etre une image")

    content = await file.read()
    if len(content) > 2 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="L'avatar ne doit pas depasser 2 Mo")

    from ..file_storage.models import StorageDocument
    from ..file_storage.services import soft_delete_document
    from ..file_storage.services import upload_file as fs_upload

    # Delete old avatar if exists
    result = await db.execute(select(User).where(User.id == current_user.id))
    user = result.scalar_one()
    if user.avatar_file_id:
        old_doc = await db.scalar(
            select(StorageDocument).where(StorageDocument.id == user.avatar_file_id)
        )
        if old_doc:
            await soft_delete_document(db, old_doc)

    try:
        doc = await fs_upload(
            db=db,
            file_data=content,
            filename=file.filename or "avatar.png",
            mime_type=file.content_type,
            user_id=current_user.id,
            resource_type="user_avatar",
            resource_id=current_user.id,
            category="avatar",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    user.avatar_file_id = doc.id
    await db.flush()

    return {
        "avatar_url": f"/api/file-storage/files/{doc.uuid}/thumbnail",
        "file_uuid": doc.uuid,
    }


@router.delete(
    "/me/avatar",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permission("file_storage.delete"))],
)
async def delete_avatar(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Remove the current user's avatar."""
    result = await db.execute(select(User).where(User.id == current_user.id))
    user = result.scalar_one()

    if user.avatar_file_id:
        from ..file_storage.models import StorageDocument
        from ..file_storage.services import soft_delete_document
        old_doc = await db.scalar(
            select(StorageDocument).where(StorageDocument.id == user.avatar_file_id)
        )
        if old_doc:
            await soft_delete_document(db, old_doc)
        user.avatar_file_id = None
        await db.flush()


# ---------------------------------------------------------------------------
#  Preferences
# ---------------------------------------------------------------------------


@router.get(
    "/me/preferences",
    dependencies=[Depends(require_permission("preference.read"))],
)
async def get_preferences(current_user=Depends(get_current_user)):
    return current_user.preferences or {}


@router.put(
    "/me/preferences",
    dependencies=[Depends(require_permission("preference.read"))],
)
async def update_preferences(
    request: Request,
    prefs: dict = Body(...),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == current_user.id))
    user = result.scalar_one_or_none()
    from sqlalchemy.orm.attributes import flag_modified
    existing: dict = user.preferences or {}
    existing.update(prefs)
    user.preferences = existing
    flag_modified(user, "preferences")
    await db.flush()

    await event_bus.emit(
        "preference.updated",
        db=db,
        actor_id=current_user.id,
        resource_type="user",
        resource_id=current_user.id,
        payload={"keys": list(prefs.keys()), "ip": request.client.host if request.client else None},
    )

    return existing


# ---------------------------------------------------------------------------
#  Password management
# ---------------------------------------------------------------------------


@router.post("/change-password")
async def change_password(
    request: ChangePasswordRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == current_user.id))
    user = result.scalar_one_or_none()

    if user.password_hash and not user.must_change_password:
        if not request.current_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Le mot de passe actuel est requis",
            )
        if not verify_password(request.current_password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Mot de passe actuel incorrect",
            )

    validate_password(request.new_password)

    user.password_hash = hash_password(request.new_password)
    user.must_change_password = False
    await db.flush()

    await event_bus.emit(
        "user.password_changed",
        db=db,
        actor_id=current_user.id,
        resource_type="user",
        resource_id=current_user.id,
        payload={"email": user.email},
    )
    return {"message": "Mot de passe modifie avec succes"}


@router.post("/forgot-password")
@limiter.limit(settings.RATE_LIMIT_FORGOT_PASSWORD)
async def forgot_password(
    data: ForgotPasswordRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Public endpoint -- sends a password reset email if the user exists and is local."""
    email = data.email.lower()
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if user and user.auth_source == "local":
        token = str(uuid.uuid4())
        await create_security_token(db, user.id, "password_reset", token, expires_minutes=30)

        try:
            from ..notification.email.services import get_email_sender

            sender = get_email_sender()
            sender.send_reset_password(
                to_email=user.email,
                to_name=f"{user.first_name} {user.last_name}",
                reset_token=token,
                initiated_by_user=True,
            )
        except Exception:
            pass

    # Always return success to prevent email enumeration
    return {"message": "Si cette adresse existe dans notre systeme, un email a ete envoye."}


@router.post("/reset-password")
@limiter.limit(settings.RATE_LIMIT_RESET_PASSWORD)
async def reset_password(
    data: ResetPasswordRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Public endpoint -- validates token and sets new password."""
    validate_password(data.new_password)

    token = await verify_security_token(db, data.token, "password_reset")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token de reinitialisation invalide ou expire",
        )

    result = await db.execute(select(User).where(User.id == token.user_id))
    target_user = result.scalar_one_or_none()
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Utilisateur introuvable",
        )

    target_user.password_hash = hash_password(data.new_password)
    target_user.must_change_password = False
    await consume_security_token(db, token)

    await event_bus.emit(
        "user.password_reset",
        db=db,
        actor_id=target_user.id,
        resource_type="user",
        resource_id=target_user.id,
        payload={"email": target_user.email},
    )
    return {"message": "Mot de passe modifie avec succes"}


@router.post("/verify-reset-token")
async def verify_reset_token_endpoint(
    request: VerifyTokenRequest,
    db: AsyncSession = Depends(get_db),
):
    """Public endpoint -- verifies if a reset token is valid without consuming it."""
    token = await verify_security_token(db, request.token, "password_reset")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token de reinitialisation invalide ou expire",
        )

    result = await db.execute(select(User).where(User.id == token.user_id))
    user = result.scalar_one_or_none()
    return {"valid": True, "email": user.email if user else None}


# ---------------------------------------------------------------------------
#  Register
# ---------------------------------------------------------------------------


def _generate_verification_code() -> str:
    return str(secrets.randbelow(900000) + 100000)


@router.post("/register", status_code=status.HTTP_201_CREATED)
@limiter.limit(settings.RATE_LIMIT_REGISTER)
async def register(
    data: RegisterRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    email = data.email.lower()
    generic_message = "Si cette adresse n'est pas deja enregistree, un code de verification a ete envoye"

    result = await db.execute(select(User).where(User.email == email))
    existing = result.scalar_one_or_none()
    if existing:
        # Anti-enumeration: return same response shape without revealing account existence
        return RegisterResponse(
            message=generic_message,
            email=email,
            email_verification_required=True,
            debug_code=None,
        )

    validate_password(data.password)

    user = User(
        email=email,
        password_hash=hash_password(data.password),
        first_name=data.first_name,
        last_name=data.last_name,
        auth_source="local",
        is_active=True,
        email_verified=False,
    )
    db.add(user)
    await db.flush()

    code = _generate_verification_code()
    await create_security_token(db, user.id, "email_verification", code, expires_minutes=5)

    if settings.EMAIL_ENABLED:
        try:
            from ..notification.email.services import get_email_sender

            sender = get_email_sender()
            sender.send_verification_code(
                to_email=user.email,
                to_name=user.first_name,
                verification_code=code,
            )
        except Exception:
            pass

    # Emit event (non-blocking — errors are logged, never propagated)
    await event_bus.emit(
        "user.registered",
        db=db,
        actor_id=user.id,
        resource_type="user",
        resource_id=user.id,
        payload={
            "actor_name": f"{user.first_name} {user.last_name}",
            "user_name": f"{user.first_name} {user.last_name}",
            "email": user.email,
        },
    )

    return RegisterResponse(
        message=generic_message,
        email=user.email,
        email_verification_required=True,
        debug_code=code if settings.is_dev else None,
    )


# ---------------------------------------------------------------------------
#  Email verification
# ---------------------------------------------------------------------------


@router.post("/verify-email", response_model=TokenResponse)
@limiter.limit("5/minute")
async def verify_email(
    data: VerifyEmailRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Verify email with 6-digit code after registration."""
    email = data.email.lower()
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=400, detail="Utilisateur introuvable")
    if user.email_verified:
        raise HTTPException(status_code=400, detail="Email deja verifie")

    token = await verify_security_token(db, data.code, "email_verification", user_id=user.id)
    if not token:
        raise HTTPException(status_code=400, detail="Code incorrect ou expire")

    user.email_verified = True
    user.email_verified_at = datetime.now(timezone.utc)
    await consume_security_token(db, token)

    await event_bus.emit(
        "user.email_verified",
        db=db,
        actor_id=user.id,
        resource_type="user",
        resource_id=user.id,
        payload={"email": user.email},
    )

    token_data = {"sub": str(user.id), "email": user.email, "lang": user.language}
    refresh = create_refresh_token(token_data)
    await _create_session(db, user.id, refresh, request)
    await db.flush()
    set_refresh_cookie(response, refresh)

    return TokenResponse(
        access_token=create_access_token(token_data),
    )


@router.post("/resend-verification")
async def resend_verification(
    data: ResendVerificationRequest,
    db: AsyncSession = Depends(get_db),
):
    """Resend verification code with 60s cooldown."""
    email = data.email.lower()
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user or user.email_verified:
        return {"message": "Si cette adresse necessite une verification, un code a ete envoye."}

    # Cooldown check
    latest = await get_latest_security_token(db, user.id, "email_verification")
    if latest:
        elapsed = (datetime.now(timezone.utc) - latest.created_at).total_seconds()
        if elapsed < 60:
            remaining = int(60 - elapsed)
            raise HTTPException(
                status_code=429,
                detail=f"Veuillez attendre {remaining} secondes avant de renvoyer un code",
            )

    code = _generate_verification_code()
    await create_security_token(db, user.id, "email_verification", code, expires_minutes=5)

    if settings.EMAIL_ENABLED:
        try:
            from ..notification.email.services import get_email_sender

            sender = get_email_sender()
            sender.send_verification_code(
                to_email=user.email,
                to_name=user.first_name,
                verification_code=code,
            )
        except Exception:
            pass

    return {
        "message": "Si cette adresse necessite une verification, un code a ete envoye.",
        "debug_code": code if settings.is_dev else None,
    }


# ---------------------------------------------------------------------------
#  Logout
# ---------------------------------------------------------------------------


@router.post("/logout", status_code=204)
async def logout(request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    """Revoke the current session and clear the refresh cookie."""
    cookie_token = request.cookies.get("refresh_token")
    if cookie_token:
        token_hash = hash_refresh_token(cookie_token)
        result = await db.execute(
            select(UserSession).where(UserSession.refresh_token_hash == token_hash)
        )
        session = result.scalar_one_or_none()
        if session and not session.is_revoked:
            session.is_revoked = True
            await db.flush()
    clear_refresh_cookie(response)


# ---------------------------------------------------------------------------
#  Session management
# ---------------------------------------------------------------------------


@router.get("/me/sessions")
async def list_my_sessions(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List active (non-revoked, non-expired) sessions for the current user."""
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(UserSession)
        .where(
            UserSession.user_id == current_user.id,
            UserSession.is_revoked.is_(False),
            UserSession.expires_at > now,
        )
        .order_by(UserSession.last_used_at.desc())
    )
    sessions = result.scalars().all()
    return [
        {
            "id": s.id,
            "ip_address": s.ip_address,
            "user_agent": s.user_agent,
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "last_used_at": s.last_used_at.isoformat() if s.last_used_at else None,
            "expires_at": s.expires_at.isoformat() if s.expires_at else None,
        }
        for s in sessions
    ]


@router.delete("/me/sessions/{session_id}", status_code=204)
async def revoke_session(
    session_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Revoke a specific session."""
    result = await db.execute(
        select(UserSession).where(
            UserSession.id == session_id,
            UserSession.user_id == current_user.id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session introuvable")
    session.is_revoked = True
    await db.flush()


@router.delete("/me/sessions", status_code=204)
async def revoke_all_sessions(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Revoke all sessions for the current user."""
    await db.execute(
        update(UserSession)
        .where(UserSession.user_id == current_user.id, UserSession.is_revoked.is_(False))
        .values(is_revoked=True)
    )
    await db.flush()


# ---------------------------------------------------------------------------
#  Account self-deletion (soft delete with reactivation window)
# ---------------------------------------------------------------------------


@router.delete("/me/account")
async def delete_my_account(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Soft-delete the current user's account.

    The account is deactivated but not purged. If the user logs in again
    within the reactivation window (default 30 days), the account is
    automatically reactivated. After that period, the scheduled purge
    command hard-deletes the data.
    """
    now = datetime.now(timezone.utc)
    current_user.deleted_at = now
    current_user.is_active = False
    # Do NOT anonymize email — allow reactivation by login
    # Email anonymization happens on hard-delete (purge command)

    # Revoke all sessions
    await db.execute(
        update(UserSession)
        .where(UserSession.user_id == current_user.id, UserSession.is_revoked.is_(False))
        .values(is_revoked=True)
    )
    await db.flush()

    await event_bus.emit(
        "user.account_deleted",
        db=db,
        actor_id=current_user.id,
        resource_type="user",
        resource_id=current_user.id,
        payload={"email": current_user.email},
    )

    return {
        "message": "Votre compte a ete desactive. Vous pouvez le reactiver en vous reconnectant dans les 30 jours.",
    }
