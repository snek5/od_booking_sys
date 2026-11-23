"""Customer email on bookings; settings table for notification switches

Revision ID: b7e2f4c81d33
Revises: a3c51e2d9b10
Create Date: 2026-11-23 13:00:00

"""
from alembic import op
import sqlalchemy as sa


revision = 'b7e2f4c81d33'
down_revision = 'a3c51e2d9b10'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('booking') as batch_op:
        batch_op.add_column(sa.Column('email', sa.String(length=254), nullable=True))
    op.create_table(
        'setting',
        sa.Column('key', sa.String(length=50), nullable=False),
        sa.Column('value', sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint('key'),
    )


def downgrade():
    op.drop_table('setting')
    with op.batch_alter_table('booking') as batch_op:
        batch_op.drop_column('email')
