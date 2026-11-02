"""Unify booking statuses and wash names; widen admin password hash

Older versions stored "Completed" (now "Attended") and "Exterior Only"
(now "Exterior"). Werkzeug's default password hashes are longer than 100
characters, which fails on Postgres/MySQL.

Revision ID: a3c51e2d9b10
Revises: 7ff104ca0e0b
Create Date: 2026-11-02 23:00:00

"""
from alembic import op
import sqlalchemy as sa


revision = 'a3c51e2d9b10'
down_revision = '7ff104ca0e0b'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("UPDATE booking SET status = 'Attended' WHERE status IN ('Completed', 'Complete')")
    op.execute("UPDATE booking SET status = 'Pending' WHERE status IS NULL")
    op.execute("UPDATE booking SET wash_type = 'Exterior' WHERE wash_type = 'Exterior Only'")
    with op.batch_alter_table('admin') as batch_op:
        batch_op.alter_column('password', existing_type=sa.String(length=100),
                              type_=sa.String(length=255), existing_nullable=False)


def downgrade():
    with op.batch_alter_table('admin') as batch_op:
        batch_op.alter_column('password', existing_type=sa.String(length=255),
                              type_=sa.String(length=100), existing_nullable=False)
    op.execute("UPDATE booking SET status = 'Completed' WHERE status = 'Attended'")
