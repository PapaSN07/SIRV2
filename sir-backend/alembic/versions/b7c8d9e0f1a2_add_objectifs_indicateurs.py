"""objectifs annuels END, SAIFI, SAIDI et défauts aux 100 km

Revision ID: b7c8d9e0f1a2
Revises: e6f7a8b9c0d1
Create Date: 2026-10-22 16:50:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b7c8d9e0f1a2"
down_revision: Union[str, None] = "e6f7a8b9c0d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "objectifs_indicateurs" not in tables:
        op.create_table(
            "objectifs_indicateurs",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("annee", sa.Integer(), nullable=False),
            sa.Column("code", sa.NVARCHAR(length=30), nullable=False),
            sa.Column("valeur_annuelle", sa.DECIMAL(18, 4), nullable=False),
            sa.Column("region_id", sa.Integer(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.text("GETDATE()"), nullable=False),
            sa.ForeignKeyConstraint(["region_id"], ["regions.id"], ondelete="NO ACTION"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_objectifs_indicateurs_annee", "objectifs_indicateurs", ["annee"])
        op.create_index("ix_objectifs_indicateurs_region_id", "objectifs_indicateurs", ["region_id"])
        op.create_index(
            "uq_objectifs_indicateurs_national",
            "objectifs_indicateurs",
            ["annee", "code"],
            unique=True,
            mssql_where=sa.text("region_id IS NULL"),
        )
        op.create_index(
            "uq_objectifs_indicateurs_region",
            "objectifs_indicateurs",
            ["annee", "code", "region_id"],
            unique=True,
            mssql_where=sa.text("region_id IS NOT NULL"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "objectifs_indicateurs" in tables:
        op.drop_table("objectifs_indicateurs")
