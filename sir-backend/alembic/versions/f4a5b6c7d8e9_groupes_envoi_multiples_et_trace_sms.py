"""Destinataires dans plusieurs groupes, exploitation des groupes, trace SMS comme SIR v1

Revision ID: f4a5b6c7d8e9
Revises: e3f4a5b6c7d8
Create Date: 2026-10-30 11:30:00.000000

SIR v1 :
- Destinataire contient une ligne par (numéro, groupe) : une personne peut appartenir à
  plusieurs groupes → table d'association destinataire_groupes (remplace destinataires.groupe_id).
- GroupeEnvoi.exploitation (BCC, BRC, DISPATCHING) et Destinataire.Matricule.
- smsenvoye.Login, Status_Code, messageID : qui a envoyé, code et identifiant renvoyés par Orange.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mssql


revision: str = "f4a5b6c7d8e9"
down_revision: Union[str, None] = "e3f4a5b6c7d8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _colonnes(inspector: sa.Inspector, table: str) -> set[str]:
    return {c["name"] for c in inspector.get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "exploitation" not in _colonnes(inspector, "groupes_envoi"):
        op.add_column("groupes_envoi", sa.Column("exploitation", mssql.NVARCHAR(20), nullable=True))

    if not inspector.has_table("destinataire_groupes"):
        op.create_table(
            "destinataire_groupes",
            sa.Column(
                "destinataire_id",
                sa.Integer(),
                sa.ForeignKey("destinataires.id", ondelete="CASCADE"),
                primary_key=True,
            ),
            sa.Column(
                "groupe_id",
                sa.Integer(),
                sa.ForeignKey("groupes_envoi.id", ondelete="CASCADE"),
                primary_key=True,
            ),
        )
        op.create_index("ix_destinataire_groupes_groupe_id", "destinataire_groupes", ["groupe_id"])

    colonnes = _colonnes(inspector, "destinataires")
    if "groupe_id" in colonnes:
        op.execute(
            sa.text(
                "INSERT INTO dbo.destinataire_groupes (destinataire_id, groupe_id) "
                "SELECT d.id, d.groupe_id FROM dbo.destinataires d "
                "WHERE d.groupe_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM dbo.destinataire_groupes x "
                "WHERE x.destinataire_id = d.id AND x.groupe_id = d.groupe_id)"
            )
        )
        op.drop_index("ix_destinataires_groupe_id", table_name="destinataires")
        op.drop_constraint("fk_destinataires_groupe_id", "destinataires", type_="foreignkey")
        op.drop_column("destinataires", "groupe_id")
    if "matricule" not in colonnes:
        op.add_column("destinataires", sa.Column("matricule", sa.Integer(), nullable=True))

    colonnes = _colonnes(inspector, "sms_envoyes")
    if "envoye_par_id" not in colonnes:
        op.add_column("sms_envoyes", sa.Column("envoye_par_id", sa.Integer(), nullable=True))
        op.create_foreign_key(
            "fk_sms_envoyes_envoye_par_id", "sms_envoyes", "utilisateurs", ["envoye_par_id"], ["id"]
        )
    if "code_retour" not in colonnes:
        op.add_column("sms_envoyes", sa.Column("code_retour", mssql.NVARCHAR(20), nullable=True))
    if "message_id" not in colonnes:
        op.add_column("sms_envoyes", sa.Column("message_id", mssql.NVARCHAR(50), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    colonnes = _colonnes(inspector, "sms_envoyes")
    for col in ("message_id", "code_retour"):
        if col in colonnes:
            op.drop_column("sms_envoyes", col)
    if "envoye_par_id" in colonnes:
        op.drop_constraint("fk_sms_envoyes_envoye_par_id", "sms_envoyes", type_="foreignkey")
        op.drop_column("sms_envoyes", "envoye_par_id")
    colonnes = _colonnes(inspector, "destinataires")
    if "matricule" in colonnes:
        op.drop_column("destinataires", "matricule")
    if "groupe_id" not in colonnes:
        op.add_column("destinataires", sa.Column("groupe_id", sa.Integer(), nullable=True))
        op.execute(
            sa.text(
                "UPDATE d SET groupe_id = (SELECT MIN(x.groupe_id) FROM dbo.destinataire_groupes x "
                "WHERE x.destinataire_id = d.id) FROM dbo.destinataires d"
            )
        )
        op.create_foreign_key(
            "fk_destinataires_groupe_id", "destinataires", "groupes_envoi", ["groupe_id"], ["id"], ondelete="SET NULL"
        )
        op.create_index("ix_destinataires_groupe_id", "destinataires", ["groupe_id"])
    if inspector.has_table("destinataire_groupes"):
        op.drop_index("ix_destinataire_groupes_groupe_id", table_name="destinataire_groupes")
        op.drop_table("destinataire_groupes")
    if "exploitation" in _colonnes(inspector, "groupes_envoi"):
        op.drop_column("groupes_envoi", "exploitation")
