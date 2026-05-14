"""baseline

Revision ID: c974f71b6305
Revises:
Create Date: 2026-05-14

Baseline миграция — фиксирует текущее состояние схемы.
Схема управляется через Base.metadata.create_all() (свежие БД)
и Alembic upgrade (будущие изменения после v10).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'c974f71b6305'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
