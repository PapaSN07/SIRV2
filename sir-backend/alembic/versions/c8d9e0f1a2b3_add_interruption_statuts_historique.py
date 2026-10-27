"""historique des statuts d'interruption (renvoi, dévalidation, archivage)

Revision ID: c8d9e0f1a2b3
Revises: b7c8d9e0f1a2
Create Date: 2026-10-27 16:10:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mssql


revision: str = "c8d9e0f1a2b3"
down_revision: Union[str, None] = "b7c8d9e0f1a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "interruption_statuts_historique"


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if _TABLE in tables:
        return
    op.create_table(
        _TABLE,
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("interruption_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.NVARCHAR(length=30), nullable=False),
        sa.Column("ancien_statut", sa.NVARCHAR(length=20), nullable=True),
        sa.Column("nouveau_statut", sa.NVARCHAR(length=20), nullable=False),
        sa.Column("motif", sa.NVARCHAR(length=1000), nullable=True),
        sa.Column("utilisateur_id", sa.Integer(), nullable=False),
        sa.Column("created_at", mssql.DATETIME2(), server_default=sa.text("GETDATE()"), nullable=False),
        sa.ForeignKeyConstraint(["interruption_id"], ["interruptions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["utilisateur_id"], ["utilisateurs.id"], ondelete="NO ACTION"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "action IN ('creation', 'cloture', 'validation', 'renvoi_correction', "
            "'devalidation', 'archivage')",
            name="ck_interruption_statut_histo_action",
        ),
    )
    op.create_index(f"ix_{_TABLE}_interruption_id", _TABLE, ["interruption_id"])
    op.create_index(f"ix_{_TABLE}_utilisateur_id", _TABLE, ["utilisateur_id"])
    op.create_index(f"ix_{_TABLE}_created_at", _TABLE, ["created_at"])


def downgrade() -> None:
    bind = op.get_bind()
    if _TABLE in set(sa.inspect(bind).get_table_names()):
        op.drop_table(_TABLE)
