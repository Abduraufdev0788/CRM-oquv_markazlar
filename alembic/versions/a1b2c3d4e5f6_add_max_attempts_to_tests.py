"""Add max_attempts to tests

Revision ID: a1b2c3d4e5f6
Revises: ac0f77243e53
Create Date: 2026-08-10 00:58:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'ac0f77243e53'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add max_attempts column with default value 1
    op.add_column('tests', sa.Column('max_attempts', sa.SmallInteger(), nullable=False, server_default='1'))


def downgrade() -> None:
    op.drop_column('tests', 'max_attempts')
