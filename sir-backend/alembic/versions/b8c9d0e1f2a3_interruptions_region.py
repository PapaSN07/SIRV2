"""Région d'exploitation portée par l'interruption (Dakar BCC / Régions BRC)

SIR v1 range chaque interruption dans « Dakar » ou « Régions » (colonne regions) ; les services
travaillent dans les deux régions. Les services représentatifs qui portent la base clients sont
rattachés à leur région : DD → Dakar, BRC → Régions.

Les interruptions existantes sont complétées par scripts/migration/backfill_interruption_region.py
(colonne regions de SIR v1).

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b8c9d0e1f2a3"
down_revision: Union[str, None] = "a7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "region_id" not in {c["name"] for c in inspector.get_columns("interruptions")}:
        op.add_column("interruptions", sa.Column("region_id", sa.Integer(), nullable=True))
        op.create_foreign_key("fk_interruptions_region_id", "interruptions", "regions", ["region_id"], ["id"])
        op.create_index("ix_interruptions_region_id", "interruptions", ["region_id"])
    # Services représentatifs de la base clients SIR v1
    op.execute(
        "UPDATE s SET region_id = r.id FROM services s JOIN regions r ON r.code = 'DAKAR' WHERE s.code = 'DD'"
    )
    op.execute(
        "UPDATE s SET region_id = r.id FROM services s JOIN regions r ON r.code = 'REGIONS' WHERE s.code = 'BRC'"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE s SET region_id = r.id FROM services s JOIN regions r ON r.code = 'DAKAR' WHERE s.code = 'BRC'"
    )
    op.drop_index("ix_interruptions_region_id", table_name="interruptions")
    op.drop_constraint("fk_interruptions_region_id", "interruptions", type_="foreignkey")
    op.drop_column("interruptions", "region_id")
