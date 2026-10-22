"""add feeder_id, service_id, poste_source_id on poste_interruptions

Revision ID: a1b2c3d4e5f6
Revises: f3a4b5c6d7e8
Create Date: 2026-07-21 12:20:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "f3a4b5c6d7e8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("poste_interruptions")}
    fks = {fk["name"] for fk in inspector.get_foreign_keys("poste_interruptions")}
    indexes = {idx["name"] for idx in inspector.get_indexes("poste_interruptions")}

    if "feeder_id" not in columns:
        op.add_column(
            "poste_interruptions",
            sa.Column("feeder_id", sa.Integer(), nullable=True),
        )
    if "service_id" not in columns:
        op.add_column(
            "poste_interruptions",
            sa.Column("service_id", sa.Integer(), nullable=True),
        )
    if "poste_source_id" not in columns:
        op.add_column(
            "poste_interruptions",
            sa.Column("poste_source_id", sa.Integer(), nullable=True),
        )

    if "fk_poste_interruptions_feeder_id" not in fks:
        op.create_foreign_key(
            "fk_poste_interruptions_feeder_id",
            "poste_interruptions",
            "feeders",
            ["feeder_id"],
            ["id"],
            ondelete="NO ACTION",
        )
    if "fk_poste_interruptions_service_id" not in fks:
        op.create_foreign_key(
            "fk_poste_interruptions_service_id",
            "poste_interruptions",
            "services",
            ["service_id"],
            ["id"],
            ondelete="NO ACTION",
        )
    if "fk_poste_interruptions_poste_source_id" not in fks:
        op.create_foreign_key(
            "fk_poste_interruptions_poste_source_id",
            "poste_interruptions",
            "postes_sources",
            ["poste_source_id"],
            ["id"],
            ondelete="NO ACTION",
        )

    if "ix_poste_interruptions_feeder_id" not in indexes:
        op.create_index(
            op.f("ix_poste_interruptions_feeder_id"),
            "poste_interruptions",
            ["feeder_id"],
            unique=False,
        )
    if "ix_poste_interruptions_service_id" not in indexes:
        op.create_index(
            op.f("ix_poste_interruptions_service_id"),
            "poste_interruptions",
            ["service_id"],
            unique=False,
        )
    if "ix_poste_interruptions_poste_source_id" not in indexes:
        op.create_index(
            op.f("ix_poste_interruptions_poste_source_id"),
            "poste_interruptions",
            ["poste_source_id"],
            unique=False,
        )

    # Dénormalisation depuis interruption + poste + feeder
    op.execute(
        sa.text(
            """
            UPDATE pi
            SET
                feeder_id = COALESCE(pi.feeder_id, i.feeder_id, p.feeder_id),
                service_id = COALESCE(
                    pi.service_id,
                    i.service_id,
                    p.service_id,
                    f.service_id
                ),
                poste_source_id = COALESCE(
                    pi.poste_source_id,
                    i.poste_source_id,
                    f.poste_source_id
                )
            FROM dbo.poste_interruptions AS pi
            INNER JOIN dbo.interruptions AS i ON i.id = pi.interruption_id
            LEFT JOIN dbo.postes AS p ON p.id = pi.poste_id
            LEFT JOIN dbo.feeders AS f
                ON f.id = COALESCE(i.feeder_id, p.feeder_id, pi.feeder_id)
            """
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("poste_interruptions")}
    fks = {fk["name"] for fk in inspector.get_foreign_keys("poste_interruptions")}
    indexes = {idx["name"] for idx in inspector.get_indexes("poste_interruptions")}

    if "ix_poste_interruptions_poste_source_id" in indexes:
        op.drop_index(
            op.f("ix_poste_interruptions_poste_source_id"),
            table_name="poste_interruptions",
        )
    if "ix_poste_interruptions_service_id" in indexes:
        op.drop_index(
            op.f("ix_poste_interruptions_service_id"),
            table_name="poste_interruptions",
        )
    if "ix_poste_interruptions_feeder_id" in indexes:
        op.drop_index(
            op.f("ix_poste_interruptions_feeder_id"),
            table_name="poste_interruptions",
        )

    if "fk_poste_interruptions_poste_source_id" in fks:
        op.drop_constraint(
            "fk_poste_interruptions_poste_source_id",
            "poste_interruptions",
            type_="foreignkey",
        )
    if "fk_poste_interruptions_service_id" in fks:
        op.drop_constraint(
            "fk_poste_interruptions_service_id",
            "poste_interruptions",
            type_="foreignkey",
        )
    if "fk_poste_interruptions_feeder_id" in fks:
        op.drop_constraint(
            "fk_poste_interruptions_feeder_id",
            "poste_interruptions",
            type_="foreignkey",
        )

    if "poste_source_id" in columns:
        op.drop_column("poste_interruptions", "poste_source_id")
    if "service_id" in columns:
        op.drop_column("poste_interruptions", "service_id")
    if "feeder_id" in columns:
        op.drop_column("poste_interruptions", "feeder_id")
