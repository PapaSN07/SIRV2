"""add interruptions.sous_feeder_id

Revision ID: f3a4b5c6d7e8
Revises: e2a6b7c8d9e0
Create Date: 2026-06-29 12:20:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f3a4b5c6d7e8"
down_revision: Union[str, None] = "e2a6b7c8d9e0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("interruptions")}

    if "sous_feeder_id" not in columns:
        op.add_column(
            "interruptions",
            sa.Column("sous_feeder_id", sa.Integer(), nullable=True),
        )
        op.create_foreign_key(
            "fk_interruptions_sous_feeder_id",
            "interruptions",
            "sous_feeders",
            ["sous_feeder_id"],
            ["id"],
            ondelete="NO ACTION",
        )
        op.create_index(
            op.f("ix_interruptions_sous_feeder_id"),
            "interruptions",
            ["sous_feeder_id"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("interruptions")}
    if "sous_feeder_id" in columns:
        op.drop_index(op.f("ix_interruptions_sous_feeder_id"), table_name="interruptions")
        op.drop_constraint("fk_interruptions_sous_feeder_id", "interruptions", type_="foreignkey")
        op.drop_column("interruptions", "sous_feeder_id")
