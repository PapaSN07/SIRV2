"""Index des tronçons SIG par départ et date de chargement (dernier chargement de chaque départ).

Revision ID: 1b2c3d4e5f6a
Revises: a6b7c8d9e0f1
Create Date: 2026-11-19
"""

from typing import Sequence, Union

from alembic import op

revision: str = "1b2c3d4e5f6a"
down_revision: Union[str, None] = "a6b7c8d9e0f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_troncons_sig_feeder_chargement",
        "troncons_sig",
        ["nom_feeder", "date_chargement"],
        mssql_include=["id", "feeder_id", "longueur_m"],
    )


def downgrade() -> None:
    op.drop_index("ix_troncons_sig_feeder_chargement", table_name="troncons_sig")
