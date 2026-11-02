"""Région d'exploitation propre au départ (feeders.region_id)

Certains départs de SDRBD (Dakar) alimentent les Régions : leur région se fixe départ par départ
(scripts/migration/appliquer_regions_departs.py, d'après les délégations SIG de Troncon_SIG).
Vide pour les autres départs : la région est alors celle du service.

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d0e1f2a3b4c5"
down_revision: Union[str, None] = "c9d0e1f2a3b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "region_id" not in {c["name"] for c in inspector.get_columns("feeders")}:
        op.add_column("feeders", sa.Column("region_id", sa.Integer(), nullable=True))
        op.create_foreign_key("fk_feeders_region_id", "feeders", "regions", ["region_id"], ["id"])


def downgrade() -> None:
    op.drop_constraint("fk_feeders_region_id", "feeders", type_="foreignkey")
    op.drop_column("feeders", "region_id")
