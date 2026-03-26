"""Add scope columns to roles, user_roles, invitations

Revision ID: u4v5w6x7y8z9
Revises: t3u4v5w6x7y8
Create Date: 2026-03-26

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "u4v5w6x7y8z9"
down_revision: Union[str, None] = "t3u4v5w6x7y8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. roles: add scope_type, scope_id ────────────────────────────────
    op.add_column("roles", sa.Column("scope_type", sa.String(20), nullable=False, server_default="global"))
    op.add_column("roles", sa.Column("scope_id", sa.Integer(), nullable=False, server_default="0"))

    # Replace unique constraint: slug alone → (slug, scope_type, scope_id)
    op.drop_constraint("uq_roles_slug", "roles", type_="unique")
    op.drop_index("ix_roles_slug", table_name="roles")
    op.create_unique_constraint("uq_roles_slug_scope", "roles", ["slug", "scope_type", "scope_id"])
    op.create_index("ix_roles_scope", "roles", ["scope_type", "scope_id"])

    # ── 2. user_roles: add scope_type, scope_id, is_active, created_at ───
    # Add columns first (with server defaults so existing rows get values)
    op.add_column("user_roles", sa.Column("scope_type", sa.String(20), nullable=False, server_default="global"))
    op.add_column("user_roles", sa.Column("scope_id", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("user_roles", sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"))
    op.add_column("user_roles", sa.Column("created_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.func.now()))

    # Change primary key: (user_id, role_id) → (user_id, role_id, scope_type, scope_id)
    op.execute(sa.text("ALTER TABLE user_roles DROP CONSTRAINT user_roles_pkey"))
    op.execute(sa.text(
        "ALTER TABLE user_roles ADD CONSTRAINT user_roles_pkey "
        "PRIMARY KEY (user_id, role_id, scope_type, scope_id)"
    ))

    op.create_index("ix_user_roles_scope", "user_roles", ["scope_type", "scope_id"])
    op.create_index("ix_user_roles_user_scope", "user_roles", ["user_id", "scope_type", "scope_id"])

    # ── 3. invitations: add scope_type, scope_id, role_id ────────────────
    op.add_column("invitations", sa.Column("scope_type", sa.String(20), nullable=True))
    op.add_column("invitations", sa.Column("scope_id", sa.Integer(), nullable=True))
    op.add_column("invitations", sa.Column("role_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_invitations_role_id", "invitations", "roles", ["role_id"], ["id"], ondelete="SET NULL")


def downgrade() -> None:
    # ── 3. invitations ────────────────────────────────────────────────────
    op.drop_constraint("fk_invitations_role_id", "invitations", type_="foreignkey")
    op.drop_column("invitations", "role_id")
    op.drop_column("invitations", "scope_id")
    op.drop_column("invitations", "scope_type")

    # ── 2. user_roles ────────────────────────────────────────────────────
    op.drop_index("ix_user_roles_user_scope", table_name="user_roles")
    op.drop_index("ix_user_roles_scope", table_name="user_roles")

    # Restore original PK
    op.execute(sa.text("ALTER TABLE user_roles DROP CONSTRAINT user_roles_pkey"))
    op.execute(sa.text(
        "ALTER TABLE user_roles ADD CONSTRAINT user_roles_pkey "
        "PRIMARY KEY (user_id, role_id)"
    ))

    op.drop_column("user_roles", "created_at")
    op.drop_column("user_roles", "is_active")
    op.drop_column("user_roles", "scope_id")
    op.drop_column("user_roles", "scope_type")

    # ── 1. roles ─────────────────────────────────────────────────────────
    op.drop_index("ix_roles_scope", table_name="roles")
    op.drop_constraint("uq_roles_slug_scope", "roles", type_="unique")
    op.create_unique_constraint("uq_roles_slug", "roles", ["slug"])
    op.create_index("ix_roles_slug", "roles", ["slug"], unique=True)

    op.drop_column("roles", "scope_id")
    op.drop_column("roles", "scope_type")
