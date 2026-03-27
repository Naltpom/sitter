"""add_tts_feature_state

Revision ID: b090fccfaa4f
Revises: fc8cad863ba2
Create Date: 2026-03-27 11:37:53.637922

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b090fccfaa4f'
down_revision: Union[str, None] = 'fc8cad863ba2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "INSERT INTO feature_states (name, is_active, updated_at) "
            "VALUES ('tts', true, NOW()) "
            "ON CONFLICT (name) DO NOTHING"
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM feature_states WHERE name = 'tts'"))
