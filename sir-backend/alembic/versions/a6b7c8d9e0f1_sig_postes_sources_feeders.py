"""SIG : postes sources et départs du SIG (PosteSource_SIG, FEEDERS_SIG) et colonnes complémentaires
des nœuds (délégation, région, puissance, famille, cellule) et des tronçons (matricule du départ,
section, poste source, type de conducteur, délégation, date de mise à jour).

Revision ID: a6b7c8d9e0f1
Revises: f5a6b7c8d9e0
Create Date: 2026-11-19
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a6b7c8d9e0f1"
down_revision: Union[str, None] = "f5a6b7c8d9e0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NOEUDS = [
    ("delegation", sa.NVARCHAR(100)),
    ("region", sa.NVARCHAR(100)),
    ("puissance", sa.NVARCHAR(50)),
    ("famille_poste", sa.NVARCHAR(100)),
    ("cellule", sa.NVARCHAR(100)),
]
_TRONCONS = [
    ("imat_feeder", sa.NVARCHAR(100)),
    ("section", sa.NVARCHAR(100)),
    ("poste_source", sa.NVARCHAR(255)),
    ("type_conducteur", sa.NVARCHAR(100)),
    ("delegation", sa.NVARCHAR(100)),
    ("date_maj", sa.DateTime()),
]


def upgrade() -> None:
    for nom, type_ in _NOEUDS:
        op.add_column("noeuds_sig", sa.Column(nom, type_, nullable=True))
    for nom, type_ in _TRONCONS:
        op.add_column("troncons_sig", sa.Column(nom, type_, nullable=True))

    op.create_table(
        "postes_sources_sig",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("legacy_id", sa.NVARCHAR(100), nullable=False),
        sa.Column("nom", sa.NVARCHAR(255), nullable=True),
        sa.Column("code", sa.NVARCHAR(100), nullable=True),
        sa.Column("delegation", sa.NVARCHAR(100), nullable=True),
        sa.Column("region", sa.NVARCHAR(100), nullable=True),
        sa.Column("tension", sa.NVARCHAR(50), nullable=True),
        sa.Column("coord_x", sa.Float(), nullable=True),
        sa.Column("coord_y", sa.Float(), nullable=True),
        sa.Column("attributs", sa.NVARCHAR(None), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(getdate())"), nullable=False),
        sa.UniqueConstraint("legacy_id", name="uq_postes_sources_sig_legacy_id"),
    )
    op.create_index("ix_postes_sources_sig_nom", "postes_sources_sig", ["nom"])
    op.create_index("ix_postes_sources_sig_code", "postes_sources_sig", ["code"])

    op.create_table(
        "feeders_sig",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("legacy_id", sa.NVARCHAR(100), nullable=False),
        sa.Column("nom", sa.NVARCHAR(255), nullable=True),
        sa.Column("code", sa.NVARCHAR(100), nullable=True),
        sa.Column("poste_source", sa.NVARCHAR(255), nullable=True),
        sa.Column("delegation", sa.NVARCHAR(100), nullable=True),
        sa.Column("tension", sa.NVARCHAR(50), nullable=True),
        sa.Column("feeder_id", sa.Integer(), sa.ForeignKey("feeders.id", ondelete="SET NULL"), nullable=True),
        sa.Column("attributs", sa.NVARCHAR(None), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(getdate())"), nullable=False),
        sa.UniqueConstraint("legacy_id", name="uq_feeders_sig_legacy_id"),
    )
    op.create_index("ix_feeders_sig_nom", "feeders_sig", ["nom"])
    op.create_index("ix_feeders_sig_code", "feeders_sig", ["code"])
    op.create_index("ix_feeders_sig_poste_source", "feeders_sig", ["poste_source"])
    op.create_index("ix_feeders_sig_feeder_id", "feeders_sig", ["feeder_id"])


def downgrade() -> None:
    op.drop_table("feeders_sig")
    op.drop_table("postes_sources_sig")
    for nom, _ in reversed(_TRONCONS):
        op.drop_column("troncons_sig", nom)
    for nom, _ in reversed(_NOEUDS):
        op.drop_column("noeuds_sig", nom)
