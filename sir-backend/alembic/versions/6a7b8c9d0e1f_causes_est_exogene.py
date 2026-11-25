"""Causes : drapeau « facteur exogène » (filtre du menu Suivi incidents).

Reprend Causes.FacteursExogenes de SIR v1 pour les nouvelles reprises (loader référentiel).
Pour les causes déjà en base, le drapeau est posé d'après le libellé, avec les mots du rapport
hebdo DD (choc accidentel, agression, malveillance, facteur exogène). La correction cause par
cause (écran Référentiel, reprise de FacteursExogenes pour les causes existantes) reste à faire.

Revision ID: 6a7b8c9d0e1f
Revises: 5f6a7b8c9d0e
Create Date: 2026-11-25
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "6a7b8c9d0e1f"
down_revision: Union[str, None] = "5f6a7b8c9d0e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_MOTIFS = ("%CHOC ACCIDENTEL%", "%AGRESSION%", "%MALVEILLANCE%", "%EXOG%NE%")


def upgrade() -> None:
    op.add_column(
        "causes",
        sa.Column("est_exogene", sa.Boolean(), nullable=False, server_default=sa.text("0")),
    )
    conditions = " OR ".join(f"UPPER(libelle) LIKE '{motif}'" for motif in _MOTIFS)
    op.execute(f"UPDATE causes SET est_exogene = 1 WHERE {conditions}")


def downgrade() -> None:
    # SQL Server : la contrainte DEFAULT doit disparaître avant la colonne
    op.execute(
        """
        DECLARE @contrainte NVARCHAR(256);
        SELECT @contrainte = dc.name
        FROM sys.default_constraints dc
        JOIN sys.columns c ON c.default_object_id = dc.object_id
        WHERE dc.parent_object_id = OBJECT_ID('causes') AND c.name = 'est_exogene';
        IF @contrainte IS NOT NULL EXEC('ALTER TABLE causes DROP CONSTRAINT ' + @contrainte);
        """
    )
    op.drop_column("causes", "est_exogene")
