"""Дефолт темы — тёмная (для новых профилей; существующие значения не трогаем).

Revision ID: f8a1d02c7e31
Revises: e512b5262552
Create Date: 2026-07-14
"""
import sqlalchemy as sa
from alembic import op

revision = "f8a1d02c7e31"
down_revision = "e512b5262552"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("profiles", "theme", server_default="dark")


def downgrade() -> None:
    op.alter_column("profiles", "theme", server_default="system")
