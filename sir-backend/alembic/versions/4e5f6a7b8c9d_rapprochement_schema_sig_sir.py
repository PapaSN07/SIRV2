"""Rapprochement Schéma unifilaire / SIG / SIR et postes à créer dans SIR.

- schema_unifilaire_postes : nœud SIG rapproché (noeud_sig_id, rapprochement_sig) et décision SIR
  (statut_sir : inactif = poste hors service non repris dans SIR ; a_creer = création proposée) ;
- postes_a_creer : propositions de création de poste (poste source, feeder, poste), validées ou
  rejetées par l'Admin SCR.

Revision ID: 4e5f6a7b8c9d
Revises: 3d4e5f6a7b8c
Create Date: 2026-11-23
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mssql

revision: str = "4e5f6a7b8c9d"
down_revision: Union[str, None] = "3d4e5f6a7b8c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("schema_unifilaire_postes", sa.Column("noeud_sig_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_schema_unifilaire_postes_noeud_sig", "schema_unifilaire_postes", "noeuds_sig", ["noeud_sig_id"], ["id"]
    )
    op.add_column("schema_unifilaire_postes", sa.Column("rapprochement_sig", sa.NVARCHAR(10), nullable=True))
    op.add_column("schema_unifilaire_postes", sa.Column("statut_sir", sa.NVARCHAR(10), nullable=True))
    op.create_index("ix_schema_unifilaire_postes_noeud_sig_id", "schema_unifilaire_postes", ["noeud_sig_id"])

    op.create_table(
        "postes_a_creer",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "schema_poste_id",
            sa.Integer(),
            sa.ForeignKey("schema_unifilaire_postes.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("schema_nom", sa.NVARCHAR(150), nullable=True),
        sa.Column("libelle_schema", sa.NVARCHAR(200), nullable=True),
        sa.Column("libelle", sa.NVARCHAR(200), nullable=False),
        sa.Column("poste_source_id", sa.Integer(), sa.ForeignKey("postes_sources.id", ondelete="NO ACTION"), nullable=False),
        sa.Column("feeder_id", sa.Integer(), sa.ForeignKey("feeders.id", ondelete="NO ACTION"), nullable=False),
        sa.Column("noeud_sig_id", sa.Integer(), sa.ForeignKey("noeuds_sig.id", ondelete="NO ACTION"), nullable=True),
        sa.Column("statut", sa.NVARCHAR(10), nullable=False, server_default=sa.text("'propose'")),
        sa.Column("motif_rejet", sa.NVARCHAR(500), nullable=True),
        sa.Column("poste_id", sa.Integer(), sa.ForeignKey("postes.id", ondelete="NO ACTION"), nullable=True),
        sa.Column("propose_par_id", sa.Integer(), sa.ForeignKey("utilisateurs.id", ondelete="NO ACTION"), nullable=False),
        sa.Column("propose_le", mssql.DATETIME2(), nullable=False, server_default=sa.text("(getdate())")),
        sa.Column("traite_par_id", sa.Integer(), sa.ForeignKey("utilisateurs.id", ondelete="NO ACTION"), nullable=True),
        sa.Column("traite_le", mssql.DATETIME2(), nullable=True),
    )
    op.create_index("ix_postes_a_creer_statut", "postes_a_creer", ["statut"])
    op.create_index("ix_postes_a_creer_feeder_id", "postes_a_creer", ["feeder_id"])
    op.create_index("ix_postes_a_creer_schema_poste_id", "postes_a_creer", ["schema_poste_id"])


def downgrade() -> None:
    op.drop_index("ix_postes_a_creer_schema_poste_id", table_name="postes_a_creer")
    op.drop_index("ix_postes_a_creer_feeder_id", table_name="postes_a_creer")
    op.drop_index("ix_postes_a_creer_statut", table_name="postes_a_creer")
    op.drop_table("postes_a_creer")
    op.drop_index("ix_schema_unifilaire_postes_noeud_sig_id", table_name="schema_unifilaire_postes")
    op.drop_constraint("fk_schema_unifilaire_postes_noeud_sig", "schema_unifilaire_postes", type_="foreignkey")
    op.drop_column("schema_unifilaire_postes", "statut_sir")
    op.drop_column("schema_unifilaire_postes", "rapprochement_sig")
    op.drop_column("schema_unifilaire_postes", "noeud_sig_id")
