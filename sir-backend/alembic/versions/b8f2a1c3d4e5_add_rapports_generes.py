"""add_rapports_generes

Revision ID: b8f2a1c3d4e5
Revises: 771d41b833c8
Create Date: 2026-06-12 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b8f2a1c3d4e5"
down_revision: Union[str, None] = "771d41b833c8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "rapports_generes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("task_id", sa.NVARCHAR(length=64), nullable=False),
        sa.Column("type_rapport", sa.NVARCHAR(length=40), nullable=False),
        sa.Column("format", sa.NVARCHAR(length=10), nullable=False),
        sa.Column("statut", sa.NVARCHAR(length=20), nullable=False),
        sa.Column("file_path", sa.NVARCHAR(length=500), nullable=True),
        sa.Column("file_name", sa.NVARCHAR(length=255), nullable=True),
        sa.Column("error_message", sa.NVARCHAR(length=2000), nullable=True),
        sa.Column("params_json", sa.NVARCHAR(length=4000), nullable=True),
        sa.Column("region_id", sa.Integer(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(getdate())"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(getdate())"), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["utilisateurs.id"], ondelete="NO ACTION"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_id"),
    )
    op.create_index(op.f("ix_rapports_generes_task_id"), "rapports_generes", ["task_id"], unique=True)
    op.create_index(
        op.f("ix_rapports_generes_type_rapport"), "rapports_generes", ["type_rapport"], unique=False
    )
    op.create_index(op.f("ix_rapports_generes_statut"), "rapports_generes", ["statut"], unique=False)
    op.create_index(op.f("ix_rapports_generes_region_id"), "rapports_generes", ["region_id"], unique=False)
    op.create_index(op.f("ix_rapports_generes_user_id"), "rapports_generes", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_rapports_generes_user_id"), table_name="rapports_generes")
    op.drop_index(op.f("ix_rapports_generes_region_id"), table_name="rapports_generes")
    op.drop_index(op.f("ix_rapports_generes_statut"), table_name="rapports_generes")
    op.drop_index(op.f("ix_rapports_generes_type_rapport"), table_name="rapports_generes")
    op.drop_index(op.f("ix_rapports_generes_task_id"), table_name="rapports_generes")
    op.drop_table("rapports_generes")
