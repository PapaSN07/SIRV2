"""Tronçons SIG : colonne est_dernier (dernier chargement de chaque départ), indexée.

Remplace le calcul du « dernier chargement » à chaque requête (lent sur ~480 000 tronçons) par un
indicateur calculé une fois ici, puis à chaque import SIG
(scripts/migration/import_sig_topology.py, import_sig_complements.py).

Revision ID: 2c3d4e5f6a7b
Revises: 1b2c3d4e5f6a
Create Date: 2026-11-19
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "2c3d4e5f6a7b"
down_revision: Union[str, None] = "1b2c3d4e5f6a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

RECALCUL = (
    "UPDATE dbo.troncons_sig SET est_dernier = 1",
    "UPDATE t SET est_dernier = 0 FROM dbo.troncons_sig t JOIN ("
    " SELECT nom_feeder, MAX(date_chargement) AS date_max FROM dbo.troncons_sig"
    " WHERE nom_feeder IS NOT NULL GROUP BY nom_feeder) m ON m.nom_feeder = t.nom_feeder"
    " WHERE t.date_chargement < m.date_max",
    "UPDATE dbo.troncons_sig SET est_dernier = 0 WHERE nom_feeder IS NULL AND date_chargement <"
    " (SELECT MAX(date_chargement) FROM dbo.troncons_sig WHERE nom_feeder IS NULL)",
)


def upgrade() -> None:
    op.add_column(
        "troncons_sig",
        sa.Column("est_dernier", sa.Boolean(), nullable=False, server_default=sa.text("1")),
    )
    for requete in RECALCUL:
        op.execute(requete)
    op.create_index(
        "ix_troncons_sig_est_dernier",
        "troncons_sig",
        ["est_dernier", "nom_feeder"],
        mssql_include=["feeder_id", "longueur_m", "tension_kv", "date_chargement"],
    )


def downgrade() -> None:
    op.drop_index("ix_troncons_sig_est_dernier", table_name="troncons_sig")
    with op.batch_alter_table("troncons_sig") as batch:
        batch.drop_column("est_dernier")
