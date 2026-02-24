"""add guest sessions ownership and run feedback

Revision ID: 20260223_0004
Revises: 20260223_0003
Create Date: 2026-02-23 00:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "20260223_0004"
down_revision = "20260223_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "guest_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_guest_sessions_token", "guest_sessions", ["token"], unique=True)

    op.add_column("meetings", sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_index("ix_meetings_session_id", "meetings", ["session_id"], unique=False)
    op.create_foreign_key(
        "fk_meetings_session_id_guest_sessions",
        "meetings",
        "guest_sessions",
        ["session_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "run_feedback",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("meeting_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("verdict", sa.String(length=20), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["meeting_id"], ["meetings.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["guest_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_run_feedback_run_id", "run_feedback", ["run_id"], unique=False)
    op.create_index("ix_run_feedback_meeting_id", "run_feedback", ["meeting_id"], unique=False)
    op.create_index("ix_run_feedback_session_id", "run_feedback", ["session_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_run_feedback_session_id", table_name="run_feedback")
    op.drop_index("ix_run_feedback_meeting_id", table_name="run_feedback")
    op.drop_index("ix_run_feedback_run_id", table_name="run_feedback")
    op.drop_table("run_feedback")

    op.drop_constraint("fk_meetings_session_id_guest_sessions", "meetings", type_="foreignkey")
    op.drop_index("ix_meetings_session_id", table_name="meetings")
    op.drop_column("meetings", "session_id")

    op.drop_index("ix_guest_sessions_token", table_name="guest_sessions")
    op.drop_table("guest_sessions")
