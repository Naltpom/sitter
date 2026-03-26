"""fixtures_bootstrap: roles, permissions, global_permissions, feature_states, app_settings.

Revision ID: h1i2j3k4l5m6
Revises: 166f8974a0fb
Create Date: 2026-02-22 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "h1i2j3k4l5m6"
down_revision: Union[str, None] = "166f8974a0fb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ── All permission codes from feature manifests ──────────────────────────

ALL_PERMISSIONS = [
    # _identity
    ("users.read", "_identity"),
    ("users.create", "_identity"),
    ("users.update", "_identity"),
    ("users.delete", "_identity"),
    ("roles.read", "_identity"),
    ("roles.create", "_identity"),
    ("roles.update", "_identity"),
    ("roles.delete", "_identity"),
    ("permissions.read", "_identity"),
    ("permissions.manage", "_identity"),
    ("features.read", "_identity"),
    ("features.manage", "_identity"),
    ("settings.read", "_identity"),
    ("settings.manage", "_identity"),
    ("invitations.create", "_identity"),
    ("invitations.read", "_identity"),
    ("invitations.delete", "_identity"),
    ("impersonation.start", "_identity"),
    ("impersonation.read", "_identity"),
    ("backups.create", "_identity"),
    ("backups.restore", "_identity"),
    ("backups.read", "_identity"),
    ("search.global", "_identity"),
    ("commands.read", "_identity"),
    ("commands.manage", "_identity"),
    # event
    ("event.read", "event"),
    # i18n
    ("i18n.read", "i18n"),
    # mfa
    ("mfa.manage", "mfa"),
    ("mfa.setup", "mfa"),
    ("mfa.bypass", "mfa"),
    ("mfa.totp.setup", "mfa.totp"),
    ("mfa.email.setup", "mfa.email"),
    # notification
    ("notification.read", "notification"),
    ("notification.delete", "notification"),
    ("notification.admin", "notification"),
    ("notification.rules.read", "notification"),
    ("notification.rules.create", "notification"),
    ("notification.rules.update", "notification"),
    ("notification.rules.delete", "notification"),
    ("notification.email.resend", "notification.email"),
    ("notification.push.subscribe", "notification.push"),
    ("notification.push.read", "notification.push"),
    ("notification.webhook.read", "notification.webhook"),
    ("notification.webhook.create", "notification.webhook"),
    ("notification.webhook.update", "notification.webhook"),
    ("notification.webhook.delete", "notification.webhook"),
    ("notification.webhook.test", "notification.webhook"),
    ("notification.webhook.global.read", "notification.webhook"),
    ("notification.webhook.global.create", "notification.webhook"),
    ("notification.webhook.global.update", "notification.webhook"),
    ("notification.webhook.global.delete", "notification.webhook"),
    # preference
    ("preference.read", "preference"),
    ("preference.theme.read", "preference.theme"),
    ("preference.couleur.read", "preference.couleur"),
    ("preference.langue.read", "preference.langue"),
    ("preference.font.read", "preference.font"),
    ("preference.layout.read", "preference.layout"),
    ("preference.accessibilite.read", "preference.accessibilite"),
    ("preference.composants.read", "preference.composants"),
    ("preference.didacticiel.read", "preference.didacticiel"),
    ("preference.didacticiel.manage", "preference.didacticiel"),
    # rgpd
    ("rgpd.read", "rgpd"),
    ("rgpd.consentement.read", "rgpd.consentement"),
    ("rgpd.consentement.manage", "rgpd.consentement"),
    ("rgpd.registre.read", "rgpd.registre"),
    ("rgpd.registre.manage", "rgpd.registre"),
    ("rgpd.droits.read", "rgpd.droits"),
    ("rgpd.droits.manage", "rgpd.droits"),
    ("rgpd.export.read", "rgpd.export"),
    ("rgpd.politique.read", "rgpd.politique"),
    ("rgpd.politique.manage", "rgpd.politique"),
    ("rgpd.audit.read", "rgpd.audit"),
    # sso
    ("sso.link", "sso"),
    ("sso.google.login", "sso.google"),
    ("sso.github.login", "sso.github"),
    # storybook
    ("storybook.read", "storybook"),
    # onboarding
    ("onboarding.read", "onboarding"),
]

# ── Global permissions (every authenticated user) ────────────────────────

GLOBAL_PERMISSION_CODES = [
    # Lecture
    "notification.read", "event.read", "i18n.read", "search.global",
    "preference.read", "preference.theme.read", "preference.couleur.read",
    "preference.langue.read", "preference.font.read", "preference.layout.read",
    "preference.accessibilite.read", "preference.composants.read",
    "preference.didacticiel.read",
    "rgpd.read", "rgpd.consentement.read", "rgpd.droits.read",
    "rgpd.export.read", "rgpd.politique.read",
    "storybook.read",
    "onboarding.read",
    # Personnel
    "notification.delete", "notification.rules.read",
    "notification.push.subscribe", "notification.push.read",
    "notification.webhook.read", "notification.webhook.create",
    "notification.webhook.update", "notification.webhook.delete",
    "notification.webhook.test",
    # Auth / MFA / SSO
    "mfa.setup", "mfa.totp.setup", "mfa.email.setup",
    "sso.link", "sso.google.login", "sso.github.login",
]

def upgrade() -> None:
    conn = op.get_bind()

    # ── 1. Insert all permissions (idempotent) ────────────────────────────
    for code, feature in ALL_PERMISSIONS:
        conn.execute(
            sa.text(
                "INSERT INTO permissions (code, feature) "
                "VALUES (:code, :feature) "
                "ON CONFLICT (code) DO NOTHING"
            ),
            {"code": code, "feature": feature},
        )

    # ── 2. Create super_admin role (only role created by migration) ─────
    conn.execute(sa.text(
        "INSERT INTO roles (name, description, created_at, updated_at) VALUES "
        "('super_admin', 'Super administrateur — toutes les permissions', NOW(), NOW()) "
        "ON CONFLICT (name) DO NOTHING"
    ))

    # ── 3. super_admin role → ALL permissions ─────────────────────────────
    conn.execute(sa.text(
        "INSERT INTO role_permissions (role_id, permission_id) "
        "SELECT r.id, p.id FROM roles r CROSS JOIN permissions p "
        "WHERE r.name = 'super_admin' "
        "ON CONFLICT DO NOTHING"
    ))

    # ── 4. Global permissions (every authenticated user) ──────────────────
    codes_literal = ", ".join(f"'{c}'" for c in GLOBAL_PERMISSION_CODES)
    conn.execute(sa.text(f"""
        INSERT INTO global_permissions (permission_id, granted)
        SELECT id, true FROM permissions WHERE code IN ({codes_literal})
        ON CONFLICT (permission_id) DO NOTHING
    """))

    # ── 5. Default feature states ─────────────────────────────────────────
    conn.execute(sa.text("""
        INSERT INTO feature_states (name, is_active, updated_at) VALUES
            ('notification', true, NOW()),
            ('notification.email', true, NOW()),
            ('notification.push', false, NOW()),
            ('notification.webhook', true, NOW())
        ON CONFLICT (name) DO NOTHING
    """))

    # ── 6. Default app settings ───────────────────────────────────────────
    conn.execute(sa.text("""
        INSERT INTO app_settings (key, value, updated_at) VALUES
            ('app_name', 'Sitter', NOW()),
            ('app_description', '', NOW()),
            ('app_logo', '/logo_full.svg', NOW()),
            ('app_favicon', '/favicon.svg', NOW()),
            ('primary_color', '#1E40AF', NOW()),
            ('support_email', '', NOW())
        ON CONFLICT (key) DO NOTHING
    """))


def downgrade() -> None:
    conn = op.get_bind()

    # Remove app settings
    conn.execute(sa.text(
        "DELETE FROM app_settings WHERE key IN "
        "('app_name', 'app_description', 'app_logo', 'app_favicon', 'primary_color', 'support_email')"
    ))

    # Remove feature states
    conn.execute(sa.text(
        "DELETE FROM feature_states WHERE name IN "
        "('notification', 'notification.email', 'notification.push', 'notification.webhook')"
    ))

    # Remove global permissions
    conn.execute(sa.text("DELETE FROM global_permissions"))

    # Remove role permissions and super_admin role
    conn.execute(sa.text(
        "DELETE FROM role_permissions WHERE role_id IN "
        "(SELECT id FROM roles WHERE name = 'super_admin')"
    ))
    conn.execute(sa.text("DELETE FROM roles WHERE name = 'super_admin'"))
