"""add types_reseaux and interruption type_end_id / type_reseau_id

Revision ID: e6f7a8b9c0d1
Revises: d5e6f7a8b9c0
Create Date: 2026-10-20 11:40:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e6f7a8b9c0d1"
down_revision: Union[str, None] = "d5e6f7a8b9c0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns(inspector, table: str) -> set[str]:
    return {col["name"] for col in inspector.get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "types_reseaux" not in tables:
        op.create_table(
            "types_reseaux",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("code", sa.NVARCHAR(length=20), nullable=False),
            sa.Column("libelle", sa.NVARCHAR(length=200), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("code", name="uq_types_reseaux_code"),
        )

    cols = _columns(inspector, "interruptions")
    if "type_end_id" not in cols:
        op.add_column("interruptions", sa.Column("type_end_id", sa.Integer(), nullable=True))
        op.create_foreign_key(
            "fk_interruptions_type_end_id",
            "interruptions",
            "types_end",
            ["type_end_id"],
            ["id"],
            ondelete="NO ACTION",
        )
        op.create_index("ix_interruptions_type_end_id", "interruptions", ["type_end_id"])
    if "type_reseau_id" not in cols:
        op.add_column("interruptions", sa.Column("type_reseau_id", sa.Integer(), nullable=True))
        op.create_foreign_key(
            "fk_interruptions_type_reseau_id",
            "interruptions",
            "types_reseaux",
            ["type_reseau_id"],
            ["id"],
            ondelete="NO ACTION",
        )
        op.create_index("ix_interruptions_type_reseau_id", "interruptions", ["type_reseau_id"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = _columns(inspector, "interruptions")
    if "type_reseau_id" in cols:
        op.drop_index("ix_interruptions_type_reseau_id", table_name="interruptions")
        op.drop_constraint("fk_interruptions_type_reseau_id", "interruptions", type_="foreignkey")
        op.drop_column("interruptions", "type_reseau_id")
    if "type_end_id" in cols:
        op.drop_index("ix_interruptions_type_end_id", table_name="interruptions")
        op.drop_constraint("fk_interruptions_type_end_id", "interruptions", type_="foreignkey")
        op.drop_column("interruptions", "type_end_id")
    tables = set(inspector.get_table_names())
    if "types_reseaux" in tables:
        op.drop_table("types_reseaux")
