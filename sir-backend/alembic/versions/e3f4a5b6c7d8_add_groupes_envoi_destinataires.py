"""Groupes d'envoi SMS et fonction des destinataires (reprise du Répertoire SIR v1)

Revision ID: e3f4a5b6c7d8
Revises: d9e0f1a2b3c4
Create Date: 2026-10-30 10:30:00.000000

SIR v1 : tables GroupeEnvoi (Groupe) et Destinataire (prénomnom, Telephone, Fonctiondes,
Service, Groupe). La page SMS sélectionnait les destinataires par groupe.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mssql


revision: str = "e3f4a5b6c7d8"
down_revision: Union[str, None] = "d9e0f1a2b3c4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("groupes_envoi"):
        op.create_table(
            "groupes_envoi",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("libelle", mssql.NVARCHAR(255), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            sa.UniqueConstraint("libelle", name="uq_groupes_envoi_libelle"),
        )
    colonnes = {c["name"] for c in inspector.get_columns("destinataires")}
    if "fonction" not in colonnes:
        op.add_column("destinataires", sa.Column("fonction", mssql.NVARCHAR(100), nullable=True))
    if "groupe_id" not in colonnes:
        op.add_column("destinataires", sa.Column("groupe_id", sa.Integer(), nullable=True))
        op.create_foreign_key(
            "fk_destinataires_groupe_id", "destinataires", "groupes_envoi", ["groupe_id"], ["id"], ondelete="SET NULL"
        )
        op.create_index("ix_destinataires_groupe_id", "destinataires", ["groupe_id"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    colonnes = {c["name"] for c in inspector.get_columns("destinataires")}
    if "groupe_id" in colonnes:
        op.drop_index("ix_destinataires_groupe_id", table_name="destinataires")
        op.drop_constraint("fk_destinataires_groupe_id", "destinataires", type_="foreignkey")
        op.drop_column("destinataires", "groupe_id")
    if "fonction" in colonnes:
        op.drop_column("destinataires", "fonction")
    if inspector.has_table("groupes_envoi"):
        op.drop_table("groupes_envoi")
