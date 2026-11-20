"""Schémas unifilaires : schéma, postes cliquables, tuiles d'affichage.

Remplis par scripts/migration/import_schema_unifilaire.py (lecture du PDF AutoCAD).

Revision ID: 3d4e5f6a7b8c
Revises: 2c3d4e5f6a7b
Create Date: 2026-11-20
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mssql

revision: str = "3d4e5f6a7b8c"
down_revision: Union[str, None] = "2c3d4e5f6a7b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "schemas_unifilaires",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("nom", sa.NVARCHAR(150), nullable=False),
        sa.Column("fichier", sa.NVARCHAR(255), nullable=False),
        sa.Column("region_id", sa.Integer(), sa.ForeignKey("regions.id", ondelete="NO ACTION"), nullable=True),
        sa.Column("largeur", sa.Float(), nullable=False),
        sa.Column("hauteur", sa.Float(), nullable=False),
        sa.Column("zoom_max", sa.Integer(), nullable=False),
        sa.Column("graphe", sa.LargeBinary(), nullable=False),
        sa.Column("nb_postes", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("importe_le", mssql.DATETIME2(), nullable=False, server_default=sa.text("(getdate())")),
    )
    op.create_index("ix_schemas_unifilaires_region_id", "schemas_unifilaires", ["region_id"])
    op.create_table(
        "schema_unifilaire_postes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "schema_id",
            sa.Integer(),
            sa.ForeignKey("schemas_unifilaires.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("rang", sa.Integer(), nullable=False),
        sa.Column("libelle", sa.NVARCHAR(200), nullable=True),
        sa.Column("forme", sa.NVARCHAR(10), nullable=False),
        sa.Column("puissance_kva", sa.Integer(), nullable=True),
        sa.Column("x0", sa.Float(), nullable=False),
        sa.Column("y0", sa.Float(), nullable=False),
        sa.Column("x1", sa.Float(), nullable=False),
        sa.Column("y1", sa.Float(), nullable=False),
        sa.Column("lx0", sa.Float(), nullable=True),
        sa.Column("ly0", sa.Float(), nullable=True),
        sa.Column("lx1", sa.Float(), nullable=True),
        sa.Column("ly1", sa.Float(), nullable=True),
        sa.Column("poste_id", sa.Integer(), sa.ForeignKey("postes.id", ondelete="NO ACTION"), nullable=True),
        sa.Column("rapprochement", sa.NVARCHAR(10), nullable=True),
        sa.UniqueConstraint("schema_id", "rang", name="uq_schema_unifilaire_postes_rang"),
    )
    op.create_index("ix_schema_unifilaire_postes_schema_id", "schema_unifilaire_postes", ["schema_id"])
    op.create_index("ix_schema_unifilaire_postes_poste_id", "schema_unifilaire_postes", ["poste_id"])
    op.create_table(
        "schema_unifilaire_tuiles",
        sa.Column(
            "schema_id",
            sa.Integer(),
            sa.ForeignKey("schemas_unifilaires.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("z", sa.SmallInteger(), nullable=False),
        sa.Column("x", sa.SmallInteger(), nullable=False),
        sa.Column("y", sa.SmallInteger(), nullable=False),
        sa.Column("contenu", sa.LargeBinary(), nullable=False),
        sa.PrimaryKeyConstraint("schema_id", "z", "x", "y", name="pk_schema_unifilaire_tuiles"),
    )


def downgrade() -> None:
    op.drop_table("schema_unifilaire_tuiles")
    op.drop_index("ix_schema_unifilaire_postes_poste_id", table_name="schema_unifilaire_postes")
    op.drop_index("ix_schema_unifilaire_postes_schema_id", table_name="schema_unifilaire_postes")
    op.drop_table("schema_unifilaire_postes")
    op.drop_index("ix_schemas_unifilaires_region_id", table_name="schemas_unifilaires")
    op.drop_table("schemas_unifilaires")
