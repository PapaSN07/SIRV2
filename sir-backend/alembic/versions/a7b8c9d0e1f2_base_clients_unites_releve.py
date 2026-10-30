"""Base clients SAIFI/SAIDI : contrats par unité de relève et lien poste ↔ unité de relève

Revision ID: a7b8c9d0e1f2
Revises: f4a5b6c7d8e9
Create Date: 2026-10-30 12:00:00.000000

Reprise de l'application bureau SIR (atelier SAIFI/SAIDI) :
- contrats_unites_releve : photo mensuelle des contrats par unité de relève (UR), lue dans
  BI_ODS.dbo.CONTRATS_PAR_AGENCE_UR (SSIS) ou dans le fichier nombredeclientsh2mc_MMAAAA.xlsx ;
- postes_unites_releve : UR rattachées à chaque poste (SIR v1 : PosteClient), avec validation.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mssql


revision: str = "a7b8c9d0e1f2"
down_revision: Union[str, None] = "f4a5b6c7d8e9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("contrats_unites_releve"):
        op.create_table(
            "contrats_unites_releve",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("annee", sa.Integer(), nullable=False),
            sa.Column("mois", sa.Integer(), nullable=False),
            sa.Column("unite_releve", mssql.NVARCHAR(20), nullable=False),
            sa.Column("libelle", mssql.NVARCHAR(150), nullable=True),
            sa.Column("code_agence", mssql.NVARCHAR(10), nullable=True),
            sa.Column("delegation", mssql.NVARCHAR(10), nullable=True),
            sa.Column("agence_id", sa.Integer(), sa.ForeignKey("agences.id"), nullable=True),
            sa.Column("nb_contrats", sa.Integer(), nullable=False),
            sa.Column("date_maj", mssql.DATETIME2(), nullable=True),
            sa.Column("source", mssql.NVARCHAR(20), nullable=False),
            sa.UniqueConstraint("annee", "mois", "unite_releve", name="uq_contrats_ur_mois"),
            sa.CheckConstraint("mois BETWEEN 1 AND 12", name="ck_contrats_ur_mois"),
        )
        op.create_index("ix_contrats_ur_periode", "contrats_unites_releve", ["annee", "mois"])
    if not inspector.has_table("postes_unites_releve"):
        op.create_table(
            "postes_unites_releve",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("poste_id", sa.Integer(), sa.ForeignKey("postes.id", ondelete="CASCADE"), nullable=False),
            sa.Column("unite_releve", mssql.NVARCHAR(20), nullable=False),
            sa.Column("statut", mssql.NVARCHAR(25), nullable=False, server_default="valide"),
            sa.Column("modifie_par_id", sa.Integer(), sa.ForeignKey("utilisateurs.id"), nullable=True),
            sa.Column("modifie_le", mssql.DATETIME2(), nullable=True),
            sa.Column("valide_par_id", sa.Integer(), sa.ForeignKey("utilisateurs.id"), nullable=True),
            sa.Column("valide_le", mssql.DATETIME2(), nullable=True),
            sa.UniqueConstraint("poste_id", "unite_releve", name="uq_poste_ur"),
            sa.CheckConstraint(
                "statut IN ('valide', 'ajout_propose', 'suppression_proposee')", name="ck_poste_ur_statut"
            ),
        )
        op.create_index("ix_postes_ur_unite", "postes_unites_releve", ["unite_releve"])
        op.create_index("ix_postes_ur_poste", "postes_unites_releve", ["poste_id"])


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("postes_unites_releve"):
        op.drop_table("postes_unites_releve")
    if inspector.has_table("contrats_unites_releve"):
        op.drop_table("contrats_unites_releve")
