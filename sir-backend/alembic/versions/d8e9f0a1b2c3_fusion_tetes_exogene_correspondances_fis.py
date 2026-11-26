"""fusion des têtes est_exogene et correspondances_fis

Revision ID: d8e9f0a1b2c3
Revises: 6a7b8c9d0e1f, c7f1a2b3d4e5
Create Date: 2026-11-26 02:17:13.228855

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd8e9f0a1b2c3'
down_revision: Union[str, None] = ('6a7b8c9d0e1f', 'c7f1a2b3d4e5')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
