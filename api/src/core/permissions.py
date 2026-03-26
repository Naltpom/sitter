"""Permission checking system with granular feature.action permissions."""

import logging
from dataclasses import dataclass, field

from cachetools import TTLCache
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .database import get_db
from .security import get_current_user

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
#  PermissionGrant — carries scope information per permission
# ---------------------------------------------------------------------------


@dataclass
class PermissionGrant:
    is_global: bool = False
    scopes: dict[str, list[int]] = field(default_factory=dict)

    @property
    def granted(self) -> bool:
        return self.is_global or any(bool(ids) for ids in self.scopes.values())


# In-process TTL cache: key = user_id (int), value = effective permission dict
_permission_cache: TTLCache = TTLCache(
    maxsize=settings.PERMISSION_CACHE_MAX_SIZE,
    ttl=settings.PERMISSION_CACHE_TTL_SECONDS,
)


def invalidate_permission_cache(user_id: int | None = None) -> None:
    """Invalidate cached permissions.

    If *user_id* is given, only that user's entry is evicted.
    If *user_id* is ``None``, the entire cache is cleared (use after
    role-definition or global-permission changes).
    """
    if user_id is not None:
        _permission_cache.pop(user_id, None)
        logger.debug("Permission cache invalidated for user %s", user_id)
    else:
        _permission_cache.clear()
        logger.debug("Permission cache fully cleared")


# ---------------------------------------------------------------------------
#  Core loader — scoped permissions
# ---------------------------------------------------------------------------


async def load_user_scoped_permissions(db: AsyncSession, user_id: int) -> dict[str, PermissionGrant]:
    """
    Load the effective permission set for a user with full scope information.

    Resolution order:
    1. GlobalPermission → is_global=True
    2. RolePermission via UserRole → global scope → is_global, other → scopes[scope_type]
    3. UserPermission (override) → granted=True → is_global, granted=False → remove

    Results are cached in-process with a TTL.
    """
    cached = _permission_cache.get(user_id)
    if cached is not None:
        return cached

    from ._identity.models import (
        GlobalPermission,
        Permission,
        RolePermission,
        UserPermission,
        UserRole,
    )

    grants: dict[str, PermissionGrant] = {}

    # 1. Global permissions (apply to all authenticated users)
    result = await db.execute(
        select(Permission.code, GlobalPermission.granted).join(
            GlobalPermission, GlobalPermission.permission_id == Permission.id
        )
    )
    for code, granted in result.all():
        if granted:
            grants[code] = PermissionGrant(is_global=True)

    # 2. Role permissions from ALL user roles (global + scoped)
    #    Inactive scoped memberships (is_active=False) are excluded.
    result = await db.execute(
        select(Permission.code, UserRole.scope_type, UserRole.scope_id).distinct()
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .join(UserRole, UserRole.role_id == RolePermission.role_id)
        .where(UserRole.user_id == user_id, UserRole.is_active == True)  # noqa: E712
    )
    for code, scope_type, scope_id in result.all():
        if code not in grants:
            grants[code] = PermissionGrant()
        grant = grants[code]

        if scope_type == "global":
            grant.is_global = True
        elif scope_id:
            if scope_type not in grant.scopes:
                grant.scopes[scope_type] = []
            if scope_id not in grant.scopes[scope_type]:
                grant.scopes[scope_type].append(scope_id)

    # 3. User-specific permissions (highest priority)
    result = await db.execute(
        select(Permission.code, UserPermission.granted).join(
            UserPermission, UserPermission.permission_id == Permission.id
        ).where(UserPermission.user_id == user_id)
    )
    for code, granted in result.all():
        if granted:
            if code not in grants:
                grants[code] = PermissionGrant(is_global=True)
            else:
                grants[code].is_global = True
        else:
            grants.pop(code, None)

    _permission_cache[user_id] = grants
    return grants


# ---------------------------------------------------------------------------
#  Backward-compatible wrapper
# ---------------------------------------------------------------------------


async def load_user_permissions(db: AsyncSession, user_id: int) -> dict[str, bool | None]:
    """
    Backward-compatible wrapper: returns {code: True/False/None}.

    Delegates to load_user_scoped_permissions internally.
    """
    scoped = await load_user_scoped_permissions(db, user_id)
    return {code: True for code, grant in scoped.items() if grant.granted}


def require_permission(*codes: str):
    """
    FastAPI dependency factory for checking permissions.

    Usage:
        @router.get("/", dependencies=[Depends(require_permission("notification.read"))])
    """

    async def checker(
        current_user=Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ):
        user_perms = await load_user_permissions(db, current_user.id)
        for code in codes:
            granted = user_perms.get(code)
            if granted is False:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permission refusée: {code}",
                )
            if granted is not True:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permission requise: {code}",
                )
        return current_user

    return checker


def require_any_permission(*codes: str):
    """
    FastAPI dependency: user must have at least ONE of the listed permissions.

    Usage:
        @router.get("/", dependencies=[Depends(require_any_permission("a.read", "b.read"))])
    """

    async def checker(
        current_user=Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ):
        user_perms = await load_user_permissions(db, current_user.id)
        if not any(user_perms.get(code) is True for code in codes):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission requise (au moins une): {', '.join(codes)}",
            )
        return current_user

    return checker


def require_feature(feature_name: str):
    """
    FastAPI dependency that checks if a feature is active.
    Used in dev mode when all routes are registered.
    """

    async def checker(request: Request):
        registry = request.app.state.feature_registry
        if not registry.is_active(feature_name):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Feature '{feature_name}' is disabled",
            )

    return checker


async def get_user_permission_codes(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[str]:
    """Return list of permission codes the current user has. Used by /auth/me endpoint."""
    perms = await load_user_permissions(db, current_user.id)
    return [code for code, granted in perms.items() if granted is True]
