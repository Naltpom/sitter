"""FastAPI application entry point with feature-based module loading."""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded
from sqlalchemy import select

from .core.command_registry import CommandRegistry
from .core.config import settings
from .core.database import async_session
from .core.feature_registry import FeatureGateMiddleware, FeatureRegistry
from .core.rate_limit import limiter, rate_limit_exceeded_handler

logger = logging.getLogger(__name__)

# Ensure directories exist
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
os.makedirs(settings.BACKUP_DIR, exist_ok=True)

# Global feature registry
registry = FeatureRegistry()


def load_feature_states_sync() -> dict[str, bool]:
    """Load feature states from DB at startup (sync, before async loop)."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    sync_engine = create_engine(settings.database_url_sync)
    states = {}
    try:
        with Session(sync_engine) as session:
            # Check if table exists first
            from sqlalchemy import inspect

            from .core._identity.models import FeatureState
            inspector = inspect(sync_engine)
            if "feature_states" in inspector.get_table_names():
                rows = session.execute(select(FeatureState)).scalars().all()
                for row in rows:
                    states[row.name] = row.is_active
    except Exception as e:
        logger.warning(f"Could not load feature states from DB: {e}. Using defaults.")
    finally:
        sync_engine.dispose()
    return states


def import_all_models():
    """Import all models from all features so Alembic can detect them."""
    import importlib
    from pathlib import Path

    from .core.feature_registry import CORE_FEATURES_DIR, PROJECT_FEATURES_DIR

    for base_dir in [CORE_FEATURES_DIR, PROJECT_FEATURES_DIR]:
        if not base_dir.exists():
            continue
        for models_path in base_dir.rglob("models.py"):
            rel = models_path.relative_to(Path(__file__).resolve().parent)
            module_name = "src." + str(rel.with_suffix("")).replace("\\", ".").replace("/", ".")
            try:
                importlib.import_module(module_name)
            except Exception as e:
                logger.warning(f"Could not import models from {module_name}: {e}")


def create_app() -> FastAPI:
    # ── Security validation ───────────────────────────────────────────
    if settings.SECRET_KEY == "dev_secret_key_change_in_production" and settings.ENV != "dev":
        raise RuntimeError(
            "FATAL: SECRET_KEY has default value in non-dev environment. "
            "Set a secure SECRET_KEY in your .env file."
        )
    if settings.ENV != "dev" and not settings.ENCRYPTION_KEY:
        raise RuntimeError(
            "FATAL: ENCRYPTION_KEY is required in production. "
            "Generate one with: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
        )
    if settings.POSTGRES_PASSWORD == "template_dev_password" and settings.ENV != "dev":
        raise RuntimeError(
            "FATAL: POSTGRES_PASSWORD has default value in non-dev environment. "
            "Set a secure POSTGRES_PASSWORD in your .env file."
        )

    application = FastAPI(
        title="Sitter",
        description="Application de gestion de pet-sitting",
        version="2026.03.10",
        lifespan=lifespan,
        docs_url="/api/docs" if settings.is_dev else None,
        openapi_url="/api/openapi.json" if settings.is_dev else None,
    )

    # ── CORS ─────────────────────────────────────────────────────────
    if settings.CORS_ORIGINS:
        origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
    else:
        origins = [settings.FRONTEND_URL]

    application.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Accept", "Accept-Language"],
        expose_headers=["Content-Disposition"],
    )

    # ── Security headers ──────────────────────────────────────────────
    from .core.middleware_security import SecurityHeadersMiddleware
    application.add_middleware(SecurityHeadersMiddleware)

    # ── Rate limiting ─────────────────────────────────────────────────
    application.state.limiter = limiter
    application.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

    # ── Import all models (for Alembic) ──────────────────────────────
    import_all_models()

    # ── Feature discovery ────────────────────────────────────────────
    registry.discover()

    # ── Load feature states from DB ──────────────────────────────────
    db_states = load_feature_states_sync()
    registry.load_states(db_states)
    registry.validate()

    # ── Maintenance mode middleware (must intercept before feature gate) ─
    from .core.maintenance_mode.middleware import MaintenanceMiddleware
    application.add_middleware(MaintenanceMiddleware)

    # ── Feature gate middleware (rejects requests to disabled features) ─
    application.add_middleware(FeatureGateMiddleware)

    # ── Register feature middleware ──────────────────────────────────
    registry.register_middleware(application)

    # ── Register feature routes ──────────────────────────────────────
    registry.register_routes(application)

    # ── Static files ─────────────────────────────────────────────────
    application.mount("/api/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")

    # ── Command discovery ────────────────────────────────────────────
    command_registry = CommandRegistry()
    command_registry.discover()
    command_registry.load_states_from_db_sync()

    # ── Store registries in app state ────────────────────────────────
    application.state.feature_registry = registry
    application.state.command_registry = command_registry

    return application


# ── Lifespan: sync permissions + bootstrap ────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle for the application."""
    from .core._identity.models import Permission, Role, RolePermission, User, UserRole
    from .core._identity.services import sync_permissions_from_registry

    # 1. Sync permissions from feature manifests
    async with async_session() as db:
        try:
            await sync_permissions_from_registry(db, registry)
            await db.commit()
            logger.info("Permissions synced from feature manifests.")
        except Exception as e:
            logger.warning(f"Could not sync permissions at startup: {e}")

    # 2. Ensure super_admin role has ALL permissions (picks up new features)
    # Permissions with assignment_rules.role=false are excluded (user-only)
    async with async_session() as db:
        try:
            slug = settings.SUPER_ADMIN_ROLE_SLUG
            role_result = await db.execute(select(Role).where(Role.slug == slug))
            sa_role = role_result.scalar_one_or_none()
            if sa_role:
                all_perms = await db.execute(
                    select(Permission.id).where(
                        Permission.assignment_rules["role"].as_boolean() == True
                    )
                )
                all_perm_ids = {row[0] for row in all_perms.all()}
                assigned = await db.execute(
                    select(RolePermission.permission_id).where(RolePermission.role_id == sa_role.id)
                )
                assigned_ids = {row[0] for row in assigned.all()}
                missing = all_perm_ids - assigned_ids
                if missing:
                    for pid in missing:
                        db.add(RolePermission(role_id=sa_role.id, permission_id=pid))
                    await db.commit()
                    logger.info(f"Added {len(missing)} new permissions to {slug} role.")
        except Exception as e:
            logger.warning(f"Could not sync {settings.SUPER_ADMIN_ROLE_SLUG} role permissions: {e}")

    # 3. Promote DEFAULT_ADMIN_EMAIL → super_admin role
    async with async_session() as db:
        try:
            slug = settings.SUPER_ADMIN_ROLE_SLUG
            admin_result = await db.execute(
                select(User).where(User.email == settings.DEFAULT_ADMIN_EMAIL.lower())
            )
            admin_user = admin_result.scalar_one_or_none()
            if admin_user:
                changed = False
                role_result = await db.execute(select(Role).where(Role.slug == slug))
                sa_role = role_result.scalar_one_or_none()
                if sa_role:
                    existing = await db.execute(
                        select(UserRole).where(
                            UserRole.user_id == admin_user.id, UserRole.role_id == sa_role.id
                        )
                    )
                    if not existing.scalar_one_or_none():
                        db.add(UserRole(user_id=admin_user.id, role_id=sa_role.id))
                        changed = True
                if changed:
                    await db.commit()
                    logger.info(f"Promoted {settings.DEFAULT_ADMIN_EMAIL} to {slug}.")
        except Exception as e:
            logger.warning(f"Could not promote admin user: {e}")

    # 4. Configure Meilisearch indexes + initial reindex (non-blocking)
    if settings.MEILISEARCH_ENABLED:
        try:
            from .core.search.services import configure_indexes

            await configure_indexes()
            logger.info("Meilisearch indexes configured.")

            from .core.tasks import enqueue

            await enqueue("search_full_reindex")
            logger.info("Initial Meilisearch reindex enqueued.")
        except Exception as e:
            logger.warning(f"Could not configure Meilisearch: {e}")

    yield  # Application runs here


app = create_app()
