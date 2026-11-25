"""SIG ArcGIS (export KMZ « DAKAR HTA », validé SENELEC) à côté du SIG de SIR v1.

- noeuds_sig / troncons_sig : source (sir_v1 | arcgis), global_id ArcGIS (unique quand présent) ;
- noeuds_sig : poste_source, statut_validation, est_actif (un nœud SIR v1 remplacé par le nœud ArcGIS du
  même poste passe à 0 : il n'est plus proposé), date_maj.
Les nœuds et tronçons ArcGIS reçoivent un legacy_id négatif (colonnes historiques non nulles et uniques).

Revision ID: 5f6a7b8c9d0e
Revises: 4e5f6a7b8c9d
Create Date: 2026-11-25
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mssql

revision: str = "5f6a7b8c9d0e"
down_revision: Union[str, None] = "4e5f6a7b8c9d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for table in ("noeuds_sig", "troncons_sig"):
        op.add_column(table, sa.Column("source", sa.NVARCHAR(20), nullable=False, server_default=sa.text("'sir_v1'")))
        op.add_column(table, sa.Column("global_id", sa.NVARCHAR(40), nullable=True))
        op.create_index(
            f"ux_{table}_global_id",
            table,
            ["global_id"],
            unique=True,
            mssql_where=sa.text("global_id IS NOT NULL"),
            sqlite_where=sa.text("global_id IS NOT NULL"),
        )
    op.add_column("noeuds_sig", sa.Column("poste_source", sa.NVARCHAR(255), nullable=True))
    op.add_column("noeuds_sig", sa.Column("statut_validation", sa.NVARCHAR(30), nullable=True))
    op.add_column("noeuds_sig", sa.Column("est_actif", sa.Boolean(), nullable=False, server_default=sa.text("1")))
    op.add_column("noeuds_sig", sa.Column("date_maj", mssql.DATETIME2(), nullable=True))
    op.create_index("ix_noeuds_sig_est_actif", "noeuds_sig", ["est_actif"])


def downgrade() -> None:
    op.drop_index("ix_noeuds_sig_est_actif", table_name="noeuds_sig")
    op.drop_column("noeuds_sig", "est_actif", mssql_drop_default=True)
    for colonne in ("date_maj", "statut_validation", "poste_source"):
        op.drop_column("noeuds_sig", colonne)
    for table in ("troncons_sig", "noeuds_sig"):
        op.drop_index(f"ux_{table}_global_id", table_name=table)
        op.drop_column(table, "global_id")
        op.drop_column(table, "source", mssql_drop_default=True)
