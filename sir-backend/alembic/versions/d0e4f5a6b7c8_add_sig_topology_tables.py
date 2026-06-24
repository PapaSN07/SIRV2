"""add_sig_topology_tables

Revision ID: d0e4f5a6b7c8
Revises: c9a3b2d4e5f6
Create Date: 2026-06-19 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d0e4f5a6b7c8"
down_revision: Union[str, None] = "c9a3b2d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "noeuds_sig",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("legacy_id", sa.Integer(), nullable=False),
        sa.Column("legacy_fid", sa.Integer(), nullable=False),
        sa.Column("nom", sa.NVARCHAR(length=255), nullable=True),
        sa.Column("nom_feeder", sa.NVARCHAR(length=255), nullable=True),
        sa.Column("feeder_id", sa.Integer(), nullable=True),
        sa.Column("station", sa.NVARCHAR(length=255), nullable=True),
        sa.Column("coord_x", sa.Float(), nullable=True),
        sa.Column("coord_y", sa.Float(), nullable=True),
        sa.Column("categorie", sa.NVARCHAR(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(getdate())"), nullable=False),
        sa.ForeignKeyConstraint(["feeder_id"], ["feeders.id"], ondelete="NO ACTION"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("legacy_fid"),
        sa.UniqueConstraint("legacy_id"),
    )
    op.create_index(op.f("ix_noeuds_sig_legacy_id"), "noeuds_sig", ["legacy_id"], unique=True)
    op.create_index(op.f("ix_noeuds_sig_legacy_fid"), "noeuds_sig", ["legacy_fid"], unique=True)
    op.create_index(op.f("ix_noeuds_sig_nom"), "noeuds_sig", ["nom"], unique=False)
    op.create_index(op.f("ix_noeuds_sig_nom_feeder"), "noeuds_sig", ["nom_feeder"], unique=False)
    op.create_index(op.f("ix_noeuds_sig_feeder_id"), "noeuds_sig", ["feeder_id"], unique=False)

    op.create_table(
        "troncons_sig",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("legacy_id", sa.Integer(), nullable=False),
        sa.Column("legacy_fid", sa.Integer(), nullable=True),
        sa.Column("nom_feeder", sa.NVARCHAR(length=255), nullable=True),
        sa.Column("feeder_id", sa.Integer(), nullable=True),
        sa.Column("nom_troncon", sa.NVARCHAR(length=255), nullable=True),
        sa.Column("nom_noeud_amont", sa.NVARCHAR(length=255), nullable=True),
        sa.Column("code_noeud_amont", sa.NVARCHAR(length=100), nullable=True),
        sa.Column("nom_noeud_aval", sa.NVARCHAR(length=255), nullable=True),
        sa.Column("code_noeud_aval", sa.NVARCHAR(length=100), nullable=True),
        sa.Column("tension_kv", sa.DECIMAL(precision=6, scale=2), nullable=True),
        sa.Column("longueur_m", sa.DECIMAL(precision=12, scale=3), nullable=True),
        sa.Column("date_chargement", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(getdate())"), nullable=False),
        sa.ForeignKeyConstraint(["feeder_id"], ["feeders.id"], ondelete="NO ACTION"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("legacy_id"),
        sa.UniqueConstraint("legacy_fid", "date_chargement", name="uq_troncons_sig_fid_chargement"),
    )
    op.create_index(op.f("ix_troncons_sig_legacy_id"), "troncons_sig", ["legacy_id"], unique=True)
    op.create_index(op.f("ix_troncons_sig_legacy_fid"), "troncons_sig", ["legacy_fid"], unique=False)
    op.create_index(op.f("ix_troncons_sig_nom_feeder"), "troncons_sig", ["nom_feeder"], unique=False)
    op.create_index(op.f("ix_troncons_sig_feeder_id"), "troncons_sig", ["feeder_id"], unique=False)
    op.create_index(
        op.f("ix_troncons_sig_code_noeud_amont"), "troncons_sig", ["code_noeud_amont"], unique=False
    )
    op.create_index(
        op.f("ix_troncons_sig_code_noeud_aval"), "troncons_sig", ["code_noeud_aval"], unique=False
    )

    op.create_foreign_key(
        "fk_interruption_workflow_steps_troncon_sig_id",
        "interruption_workflow_steps",
        "troncons_sig",
        ["troncon_sig_id"],
        ["id"],
        ondelete="NO ACTION",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_interruption_workflow_steps_troncon_sig_id",
        "interruption_workflow_steps",
        type_="foreignkey",
    )
    op.drop_index(op.f("ix_troncons_sig_code_noeud_aval"), table_name="troncons_sig")
    op.drop_index(op.f("ix_troncons_sig_code_noeud_amont"), table_name="troncons_sig")
    op.drop_index(op.f("ix_troncons_sig_feeder_id"), table_name="troncons_sig")
    op.drop_index(op.f("ix_troncons_sig_nom_feeder"), table_name="troncons_sig")
    op.drop_index(op.f("ix_troncons_sig_legacy_fid"), table_name="troncons_sig")
    op.drop_index(op.f("ix_troncons_sig_legacy_id"), table_name="troncons_sig")
    op.drop_table("troncons_sig")
    op.drop_index(op.f("ix_noeuds_sig_feeder_id"), table_name="noeuds_sig")
    op.drop_index(op.f("ix_noeuds_sig_nom_feeder"), table_name="noeuds_sig")
    op.drop_index(op.f("ix_noeuds_sig_nom"), table_name="noeuds_sig")
    op.drop_index(op.f("ix_noeuds_sig_legacy_fid"), table_name="noeuds_sig")
    op.drop_index(op.f("ix_noeuds_sig_legacy_id"), table_name="noeuds_sig")
    op.drop_table("noeuds_sig")
