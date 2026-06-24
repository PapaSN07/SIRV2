"""add_interruption_workflow_steps

Revision ID: c9a3b2d4e5f6
Revises: b8f2a1c3d4e5
Create Date: 2026-06-19 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c9a3b2d4e5f6"
down_revision: Union[str, None] = "b8f2a1c3d4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "interruption_workflow_steps",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("interruption_id", sa.Integer(), nullable=False),
        sa.Column("date_debut_declenchement", sa.DateTime(), nullable=True),
        sa.Column("date_fin_declenchement", sa.DateTime(), nullable=True),
        sa.Column("duree_declenchement_minutes", sa.Integer(), nullable=True),
        sa.Column("date_interpellation_pdm", sa.DateTime(), nullable=True),
        sa.Column("date_arrivee_pdm", sa.DateTime(), nullable=True),
        sa.Column("duree_interpellation_minutes", sa.Integer(), nullable=True),
        sa.Column("date_debut_tronconnement", sa.DateTime(), nullable=True),
        sa.Column("date_fin_tronconnement", sa.DateTime(), nullable=True),
        sa.Column("duree_tronconnement_minutes", sa.Integer(), nullable=True),
        sa.Column("troncon_id", sa.Integer(), nullable=True),
        sa.Column("troncon_sig_id", sa.Integer(), nullable=True),
        sa.Column("date_debut_localisation", sa.DateTime(), nullable=True),
        sa.Column("date_fin_localisation", sa.DateTime(), nullable=True),
        sa.Column("duree_localisation_minutes", sa.Integer(), nullable=True),
        sa.Column("date_debut_reparation", sa.DateTime(), nullable=True),
        sa.Column("date_fin_reparation", sa.DateTime(), nullable=True),
        sa.Column("duree_reparation_minutes", sa.Integer(), nullable=True),
        sa.Column("date_debut_remise", sa.DateTime(), nullable=True),
        sa.Column("date_fin_remise", sa.DateTime(), nullable=True),
        sa.Column("duree_remise_minutes", sa.Integer(), nullable=True),
        sa.Column("noeud_amont_libelle", sa.NVARCHAR(length=255), nullable=True),
        sa.Column("noeud_aval_libelle", sa.NVARCHAR(length=255), nullable=True),
        sa.Column("responsable_matricule", sa.Integer(), nullable=True),
        sa.Column("observations_workflow", sa.NVARCHAR(length=2000), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(getdate())"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(getdate())"), nullable=False),
        sa.ForeignKeyConstraint(["interruption_id"], ["interruptions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["troncon_id"], ["troncons.id"], ondelete="NO ACTION"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("interruption_id"),
    )
    op.create_index(
        op.f("ix_interruption_workflow_steps_interruption_id"),
        "interruption_workflow_steps",
        ["interruption_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_interruption_workflow_steps_troncon_id"),
        "interruption_workflow_steps",
        ["troncon_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_interruption_workflow_steps_troncon_id"),
        table_name="interruption_workflow_steps",
    )
    op.drop_index(
        op.f("ix_interruption_workflow_steps_interruption_id"),
        table_name="interruption_workflow_steps",
    )
    op.drop_table("interruption_workflow_steps")
