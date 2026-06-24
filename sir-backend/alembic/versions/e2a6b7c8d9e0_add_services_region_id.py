"""add services.region_id

Revision ID: e2a6b7c8d9e0
Revises: d0e4f5a6b7c8
Create Date: 2026-06-19 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e2a6b7c8d9e0"
down_revision: Union[str, None] = "d0e4f5a6b7c8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("services")}

    if "region_id" not in columns:
        op.add_column(
            "services",
            sa.Column("region_id", sa.Integer(), nullable=True),
        )
        op.create_foreign_key(
            "fk_services_region_id",
            "services",
            "regions",
            ["region_id"],
            ["id"],
            ondelete="NO ACTION",
        )
        op.create_index(op.f("ix_services_region_id"), "services", ["region_id"], unique=False)

    op.execute(
        """
        UPDATE s
        SET s.region_id = d.region_id
        FROM dbo.services s
        INNER JOIN dbo.agences a ON a.id = s.agence_id
        INNER JOIN dbo.delegations d ON d.id = a.delegation_id
        WHERE s.region_id IS NULL
        """
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("services")}
    if "region_id" not in columns:
        return
    op.drop_index(op.f("ix_services_region_id"), table_name="services")
    op.drop_constraint("fk_services_region_id", "services", type_="foreignkey")
    op.drop_column("services", "region_id")
