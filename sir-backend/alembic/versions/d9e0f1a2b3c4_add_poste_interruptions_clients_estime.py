"""poste_interruptions.nombre_clients_estime (numérateur SAIFI/SAIDI SENELEC)

Revision ID: d9e0f1a2b3c4
Revises: c8d9e0f1a2b3
Create Date: 2026-10-28 09:00:00.000000

Clients estimés du poste au moment de la coupure (SIR v1 : PosteInterruption.nombreclientposteEstime).
Les liens migrés portent déjà cette valeur dans nombre_clients_touches (import ITD) : elle est
recopiée ; à défaut, le nombre de clients actuel du poste.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d9e0f1a2b3c4"
down_revision: Union[str, None] = "c8d9e0f1a2b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    colonnes = {c["name"] for c in sa.inspect(bind).get_columns("poste_interruptions")}
    if "nombre_clients_estime" not in colonnes:
        op.add_column("poste_interruptions", sa.Column("nombre_clients_estime", sa.Integer(), nullable=True))
    op.execute(
        sa.text(
            """
            UPDATE pi SET nombre_clients_estime = COALESCE(pi.nombre_clients_touches, p.nombre_clients)
            FROM dbo.poste_interruptions pi
            LEFT JOIN dbo.postes p ON p.id = pi.poste_id
            WHERE pi.nombre_clients_estime IS NULL
            """
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    colonnes = {c["name"] for c in sa.inspect(bind).get_columns("poste_interruptions")}
    if "nombre_clients_estime" in colonnes:
        op.drop_column("poste_interruptions", "nombre_clients_estime")
