"""Matricule SENELEC des utilisateurs (recherche par matricule, nom, e-mail).

Revision ID: e1f2a3b4c5d6
Revises: d0e1f2a3b4c5
Create Date: 2026-11-10
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.mssql import NVARCHAR

revision: str = "e1f2a3b4c5d6"
down_revision: Union[str, None] = "d0e1f2a3b4c5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("utilisateurs", sa.Column("matricule", NVARCHAR(20), nullable=True))
    op.create_index("ix_utilisateurs_matricule", "utilisateurs", ["matricule"])


def downgrade() -> None:
    op.drop_index("ix_utilisateurs_matricule", table_name="utilisateurs")
    op.drop_column("utilisateurs", "matricule")
