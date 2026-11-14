"""Versioned research schema; later milestones add venue lifecycle tables."""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("kind", sa.String(64), nullable=False),
        sa.Column("key", sa.String(200), nullable=False, unique=True),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
    )
    op.create_index("ix_records_kind", "records", ["kind"])
    op.create_table(
        "system_state",
        sa.Column("key", sa.String(100), primary_key=True),
        sa.Column("value", sa.Text(), nullable=False),
    )
    op.create_table(
        "reservations",
        sa.Column("key", sa.String(200), primary_key=True),
        sa.Column("event_id", sa.String(200), nullable=False),
        sa.Column("amount", sa.String(80), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
    )
    op.create_index("ix_reservations_event_id", "reservations", ["event_id"])


def downgrade() -> None:
    op.drop_table("reservations")
    op.drop_table("system_state")
    op.drop_table("records")
