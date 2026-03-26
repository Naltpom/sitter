"""Core models: User, Role, Permission, FeatureState, Invitation, Impersonation, SecurityToken."""

import hashlib
import uuid as uuid_mod
from datetime import datetime, timedelta, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base

# ── Users ────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    uuid: Mapped[uuid_mod.UUID] = mapped_column(
        UUID(as_uuid=True), unique=True, nullable=False, default=uuid_mod.uuid4, index=True
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    auth_source: Mapped[str] = mapped_column(String(20), nullable=False, default="local")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    can_login: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    email_verified: Mapped[bool] = mapped_column(Boolean, default=True)
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False)
    preferences: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    language: Mapped[str] = mapped_column(String(10), nullable=False, default="fr")
    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_active: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Avatar (file_storage)
    avatar_file_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("storage_documents.id", ondelete="SET NULL", use_alter=True), nullable=True,
    )

    __table_args__ = (
        Index("ix_users_email", func.lower(email), unique=True),
    )


# ── Security Tokens ──────────────────────────────────────────────────────

class SecurityToken(Base):
    __tablename__ = "security_tokens"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    uuid: Mapped[uuid_mod.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, default=uuid_mod.uuid4
    )
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_type: Mapped[str] = mapped_column(String(30), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("uuid", name="security_tokens_uuid_key"),
        Index("ix_security_tokens_uuid", "uuid", unique=True),
        Index("ix_security_tokens_user_type", "user_id", "token_type"),
        Index("ix_security_tokens_type_expires", "token_type", "expires_at"),
        Index("ix_security_tokens_hash_type", "token_hash", "token_type"),
    )

    @staticmethod
    def hash_value(raw_value: str) -> str:
        """HMAC-SHA256 hash for token storage and lookup."""
        import hmac

        from ..config import settings
        return hmac.new(
            settings.SECRET_KEY.encode(),
            raw_value.encode(),
            hashlib.sha256,
        ).hexdigest()


# ── Roles & Permissions ─────────────────────────────────────────────────

class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    color: Mapped[str | None] = mapped_column(String(7), nullable=True)
    scope_type: Mapped[str] = mapped_column(String(20), nullable=False, default="global", server_default="global")
    scope_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    permissions = relationship("Permission", secondary="role_permissions", back_populates="roles")

    __table_args__ = (
        UniqueConstraint("slug", "scope_type", "scope_id", name="uq_roles_slug_scope"),
        Index("ix_roles_scope", "scope_type", "scope_id"),
    )


class Permission(Base):
    __tablename__ = "permissions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(200), unique=True, nullable=False, index=True)
    feature: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    assignment_rules: Mapped[dict] = mapped_column(
        JSONB,
        server_default='{"user": true, "role": true, "global": true}',
        nullable=False,
    )

    roles = relationship("Role", secondary="role_permissions", back_populates="permissions")


class RolePermission(Base):
    __tablename__ = "role_permissions"

    role_id: Mapped[int] = mapped_column(Integer, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True)
    permission_id: Mapped[int] = mapped_column(Integer, ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True)


class UserRole(Base):
    __tablename__ = "user_roles"

    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    role_id: Mapped[int] = mapped_column(Integer, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True)
    scope_type: Mapped[str] = mapped_column(String(20), nullable=False, default="global", server_default="global", primary_key=True)
    scope_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0", primary_key=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=lambda: datetime.now(timezone.utc), server_default=func.now()
    )

    __table_args__ = (
        Index("ix_user_roles_scope", "scope_type", "scope_id"),
        Index("ix_user_roles_user_scope", "user_id", "scope_type", "scope_id"),
    )


class UserPermission(Base):
    __tablename__ = "user_permissions"

    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    permission_id: Mapped[int] = mapped_column(Integer, ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True)
    granted: Mapped[bool] = mapped_column(Boolean, nullable=False)


class GlobalPermission(Base):
    __tablename__ = "global_permissions"

    permission_id: Mapped[int] = mapped_column(Integer, ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True)
    granted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


# ── Feature State ────────────────────────────────────────────────────────

class FeatureState(Base):
    __tablename__ = "feature_states"

    name: Mapped[str] = mapped_column(String(100), primary_key=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)


# ── Command State ───────────────────────────────────────────────────────

class CommandState(Base):
    __tablename__ = "command_states"

    name: Mapped[str] = mapped_column(String(100), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)


# ── Command Execution Log ────────────────────────────────────────────────

class CommandExecution(Base):
    __tablename__ = "command_executions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    command_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    command_label: Mapped[str] = mapped_column(String(200), nullable=False)
    feature: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # "success" | "error"
    result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="api")
    executed_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    executed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )

    executed_by_user = relationship("User", foreign_keys=[executed_by])


# ── Invitations ──────────────────────────────────────────────────────────

class Invitation(Base):
    __tablename__ = "invitations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    invited_by_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    token_hmac: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc) + timedelta(hours=48)
    )
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Scoped invitation fields
    scope_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    scope_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    role_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("roles.id", ondelete="SET NULL"), nullable=True
    )

    invited_by = relationship("User", foreign_keys=[invited_by_id])
    user = relationship("User", foreign_keys=[user_id])
    role = relationship("Role", foreign_keys=[role_id])


# ── Impersonation ────────────────────────────────────────────────────────

class ImpersonationLog(Base):
    __tablename__ = "impersonation_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, index=True)
    admin_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    target_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    actions_count: Mapped[int] = mapped_column(Integer, default=0)
    last_activity_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    admin_user = relationship("User", foreign_keys=[admin_user_id])
    target_user = relationship("User", foreign_keys=[target_user_id])


# ── App Settings ────────────────────────────────────────────────────────

class AppSetting(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    updated_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)


class ImpersonationAction(Base):
    __tablename__ = "impersonation_actions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("impersonation_logs.session_id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    action_type: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    resource_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    endpoint: Mapped[str | None] = mapped_column(String(255), nullable=True)
    http_method: Mapped[str | None] = mapped_column(String(10), nullable=True)
    request_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)


# ── User Sessions ──────────────────────────────────────────────────────

class UserSession(Base):
    __tablename__ = "user_sessions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    refresh_token_hash: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    last_used_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    user = relationship("User", foreign_keys=[user_id])

    __table_args__ = (
        Index("ix_user_sessions_user_active", "user_id", "is_revoked"),
    )
