"""seed_tts_generic_voices

Revision ID: afc8574b29d8
Revises: b090fccfaa4f
Create Date: 2026-03-27 14:48:37.153358

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'afc8574b29d8'
down_revision: Union[str, None] = 'b090fccfaa4f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


GENERIC_VOICES = [
    ("Siwis", "siwis", "fr_FR-siwis-medium", "#8b5cf6", "fr"),
    ("UPMC", "upmc", "fr_FR-upmc-medium", "#3b82f6", "fr"),
]


def upgrade() -> None:
    for name, slug, model, color, lang in GENERIC_VOICES:
        op.execute(
            sa.text(
                "INSERT INTO tts_voices (uuid, name, slug, voice_type, engine, piper_model_name, color, language, is_active, created_at) "
                "VALUES (gen_random_uuid()::text, :name, :slug, 'generic', 'piper', :model, :color, :lang, true, NOW()) "
                "ON CONFLICT (slug) DO NOTHING"
            ).bindparams(name=name, slug=slug, model=model, color=color, lang=lang)
        )


def downgrade() -> None:
    for _, slug, _, _, _ in GENERIC_VOICES:
        op.execute(sa.text("DELETE FROM tts_voices WHERE slug = :slug AND voice_type = 'generic'").bindparams(slug=slug))
