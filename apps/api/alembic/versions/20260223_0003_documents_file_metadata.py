"""add documents file metadata columns

Revision ID: 20260223_0003
Revises: 20260222_0002
Create Date: 2026-02-23 00:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260223_0003"
down_revision = "20260222_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("original_filename", sa.String(length=255), nullable=True))
    op.add_column("documents", sa.Column("mime_type", sa.String(length=255), nullable=True))
    op.add_column("documents", sa.Column("size_bytes", sa.Integer(), nullable=True))
    op.add_column("documents", sa.Column("storage_path", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("documents", "storage_path")
    op.drop_column("documents", "size_bytes")
    op.drop_column("documents", "mime_type")
    op.drop_column("documents", "original_filename")

