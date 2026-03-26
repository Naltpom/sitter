"""merge scope and sitter heads

Revision ID: 28efff610c1d
Revises: 24f947e13edc, u4v5w6x7y8z9
Create Date: 2026-03-26 22:46:12.631853

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '28efff610c1d'
down_revision: Union[str, None] = ('24f947e13edc', 'u4v5w6x7y8z9')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
