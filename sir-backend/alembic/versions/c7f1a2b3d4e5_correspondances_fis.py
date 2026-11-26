"""Correspondances FIS administrées : libellé du fichier FIS → nature, cause, siège ou signalisation.

Une ligne par (catégorie, libellé FIS normalisé) ; une seule clé étrangère renseignée, celle de
la catégorie ; force majeure facultative, pour une cause seulement. Lue par l'import FIS avant
la table interne et la recherche par libellé. Ne touche à aucune autre table.

Revision ID: c7f1a2b3d4e5
Revises: 5f6a7b8c9d0e
Create Date: 2026-11-26
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mssql

revision: str = "c7f1a2b3d4e5"
down_revision: Union[str, None] = "5f6a7b8c9d0e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "correspondances_fis",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("categorie", sa.NVARCHAR(20), nullable=False),
        sa.Column("libelle_fis", sa.NVARCHAR(200), nullable=False),
        sa.Column("nature_id", sa.Integer(), sa.ForeignKey("natures.id", ondelete="NO ACTION"), nullable=True),
        sa.Column("cause_id", sa.Integer(), sa.ForeignKey("causes.id", ondelete="NO ACTION"), nullable=True),
        sa.Column("siege_id", sa.Integer(), sa.ForeignKey("sieges.id", ondelete="NO ACTION"), nullable=True),
        sa.Column(
            "signalisation_id",
            sa.Integer(),
            sa.ForeignKey("signalisations.id", ondelete="NO ACTION"),
            nullable=True,
        ),
        sa.Column("is_force_majeure", sa.Boolean(), nullable=True),
        sa.Column(
            "created_by_id", sa.Integer(), sa.ForeignKey("utilisateurs.id", ondelete="NO ACTION"), nullable=False
        ),
        sa.Column("created_at", mssql.DATETIME2(), nullable=False, server_default=sa.text("(getdate())")),
        sa.UniqueConstraint("categorie", "libelle_fis", name="uq_correspondances_fis_categorie_libelle"),
        sa.CheckConstraint(
            "categorie IN ('nature', 'cause', 'siege', 'signalisation')",
            name="ck_correspondances_fis_categorie",
        ),
        sa.CheckConstraint(
            "(categorie = 'nature' AND nature_id IS NOT NULL AND cause_id IS NULL AND siege_id IS NULL "
            "AND signalisation_id IS NULL) "
            "OR (categorie = 'cause' AND cause_id IS NOT NULL AND nature_id IS NULL AND siege_id IS NULL "
            "AND signalisation_id IS NULL) "
            "OR (categorie = 'siege' AND siege_id IS NOT NULL AND nature_id IS NULL AND cause_id IS NULL "
            "AND signalisation_id IS NULL) "
            "OR (categorie = 'signalisation' AND signalisation_id IS NOT NULL AND nature_id IS NULL "
            "AND cause_id IS NULL AND siege_id IS NULL)",
            name="ck_correspondances_fis_cible",
        ),
        sa.CheckConstraint(
            "is_force_majeure IS NULL OR categorie = 'cause'",
            name="ck_correspondances_fis_force_majeure",
        ),
    )


def downgrade() -> None:
    op.drop_table("correspondances_fis")
