"""v14: api_key column on users, changes JSON on change_logs

Revision ID: a1b2c3d4e5f6
Revises: 22f186264606
Create Date: 2026-05-15
"""
from alembic import op
import sqlalchemy as sa

revision = 'a1b2c3d4e5f6'
down_revision = '22f186264606'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users') as batch:
        batch.add_column(sa.Column('api_key', sa.String(64), nullable=True))
    with op.batch_alter_table('change_logs') as batch:
        batch.add_column(sa.Column('changes', sa.JSON(), nullable=True))


def downgrade():
    with op.batch_alter_table('users') as batch:
        batch.drop_column('api_key')
    with op.batch_alter_table('change_logs') as batch:
        batch.drop_column('changes')
