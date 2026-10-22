"""add statuts, direction_sources, entreprises, prestataires + interruption columns

Revision ID: c4d5e6f7a8b9
Revises: b2c3d4e5f6a7
Create Date: 2026-10-15 12:30:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c4d5e6f7a8b9"
down_revision: Union[str, None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

STATUTS = [
    (1, "en_cours", "En cours", 1),
    (2, "cloture", "Clôturée", 2),
    (3, "valide", "Validée", 3),
    (4, "archive", "Archivée", 4),
]
DIRECTION_SOURCES = [
    (1, "distribution", "Distribution"),
    (2, "transport", "Transport"),
    (3, "omvg", "OMVG"),
]


def _columns(inspector, table: str) -> set[str]:
    return {col["name"] for col in inspector.get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "statuts" not in tables:
        op.create_table(
            "statuts",
            sa.Column("id", sa.Integer(), autoincrement=False, nullable=False),
            sa.Column("code", sa.NVARCHAR(length=20), nullable=False),
            sa.Column("libelle", sa.NVARCHAR(length=100), nullable=False),
            sa.Column("ordre", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("code", name="uq_statuts_code"),
        )
    if "direction_sources" not in tables:
        op.create_table(
            "direction_sources",
            sa.Column("id", sa.Integer(), autoincrement=False, nullable=False),
            sa.Column("code", sa.NVARCHAR(length=20), nullable=False),
            sa.Column("libelle", sa.NVARCHAR(length=100), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("code", name="uq_direction_sources_code"),
        )
    for name in ("entreprises", "prestataires"):
        if name not in tables:
            op.create_table(
                name,
                sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
                sa.Column("code", sa.NVARCHAR(length=20), nullable=False),
                sa.Column("libelle", sa.NVARCHAR(length=200), nullable=False),
                sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
                sa.PrimaryKeyConstraint("id"),
                sa.UniqueConstraint("code", name=f"uq_{name}_code"),
            )

    for sid, code, libelle, ordre in STATUTS:
        op.execute(
            sa.text(
                "IF NOT EXISTS (SELECT 1 FROM dbo.statuts WHERE id = :id) "
                "INSERT INTO dbo.statuts (id, code, libelle, ordre) VALUES (:id, :code, :libelle, :ordre)"
            ).bindparams(id=sid, code=code, libelle=libelle, ordre=ordre)
        )
    for did, code, libelle in DIRECTION_SOURCES:
        op.execute(
            sa.text(
                "IF NOT EXISTS (SELECT 1 FROM dbo.direction_sources WHERE id = :id) "
                "INSERT INTO dbo.direction_sources (id, code, libelle) VALUES (:id, :code, :libelle)"
            ).bindparams(id=did, code=code, libelle=libelle)
        )

    # --- interruptions ---
    cols = _columns(inspector, "interruptions")
    new_cols = [
        ("statut_id", "statuts"),
        ("direction_source_id", "direction_sources"),
        ("entreprise_id", "entreprises"),
        ("prestataire_id", "prestataires"),
        ("updated_by_id", "utilisateurs"),
    ]
    for col, ref in new_cols:
        if col not in cols:
            op.add_column("interruptions", sa.Column(col, sa.Integer(), nullable=True))
            op.create_foreign_key(
                f"fk_interruptions_{col}", "interruptions", ref, [col], ["id"], ondelete="NO ACTION"
            )
            op.create_index(f"ix_interruptions_{col}", "interruptions", [col])

    op.execute(
        sa.text(
            """
            UPDATE i SET statut_id = s.id
            FROM dbo.interruptions AS i
            INNER JOIN dbo.statuts AS s ON s.code = i.statut
            WHERE i.statut_id IS NULL
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE i SET direction_source_id = d.id
            FROM dbo.interruptions AS i
            INNER JOIN dbo.direction_sources AS d ON d.code = i.type_direction
            WHERE i.direction_source_id IS NULL
            """
        )
    )
    # NOT NULL après backfill (index à recréer autour de l'ALTER COLUMN)
    for col in ("statut_id", "direction_source_id"):
        op.drop_index(f"ix_interruptions_{col}", table_name="interruptions")
        op.alter_column("interruptions", col, existing_type=sa.Integer(), nullable=False)
        op.create_index(f"ix_interruptions_{col}", "interruptions", [col])

    # --- utilisateurs ---
    if "direction_source_id" not in _columns(inspector, "utilisateurs"):
        op.add_column("utilisateurs", sa.Column("direction_source_id", sa.Integer(), nullable=True))
        op.create_foreign_key(
            "fk_utilisateurs_direction_source_id",
            "utilisateurs",
            "direction_sources",
            ["direction_source_id"],
            ["id"],
            ondelete="NO ACTION",
        )
        op.create_index("ix_utilisateurs_direction_source_id", "utilisateurs", ["direction_source_id"])

    op.execute(
        sa.text(
            """
            UPDATE u SET direction_source_id = x.direction_source_id
            FROM dbo.utilisateurs AS u
            INNER JOIN (
                SELECT ur.utilisateur_id,
                       MIN(CASE
                           WHEN r.nom IN ('BCC', 'BRC', 'ADMIN_SCR') THEN 1
                           WHEN r.nom IN ('DISPATCHER', 'ADMIN_DISPATCHING') THEN 2
                       END) AS direction_source_id
                FROM dbo.user_roles AS ur
                INNER JOIN dbo.roles AS r ON r.id = ur.role_id
                GROUP BY ur.utilisateur_id
            ) AS x ON x.utilisateur_id = u.id
            WHERE u.direction_source_id IS NULL AND x.direction_source_id IS NOT NULL
            """
        )
    )

    # --- poste_interruptions ---
    if "date_interruption" not in _columns(inspector, "poste_interruptions"):
        op.add_column(
            "poste_interruptions",
            sa.Column("date_interruption", sa.DateTime(), nullable=True),
        )
    op.execute(
        sa.text(
            """
            UPDATE pi SET date_interruption = i.date_apparition
            FROM dbo.poste_interruptions AS pi
            INNER JOIN dbo.interruptions AS i ON i.id = pi.interruption_id
            WHERE pi.date_interruption IS NULL
            """
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "date_interruption" in _columns(inspector, "poste_interruptions"):
        op.drop_column("poste_interruptions", "date_interruption")

    if "direction_source_id" in _columns(inspector, "utilisateurs"):
        op.drop_index("ix_utilisateurs_direction_source_id", table_name="utilisateurs")
        op.drop_constraint("fk_utilisateurs_direction_source_id", "utilisateurs", type_="foreignkey")
        op.drop_column("utilisateurs", "direction_source_id")

    cols = _columns(inspector, "interruptions")
    for col in ("updated_by_id", "prestataire_id", "entreprise_id", "direction_source_id", "statut_id"):
        if col in cols:
            op.drop_index(f"ix_interruptions_{col}", table_name="interruptions")
            op.drop_constraint(f"fk_interruptions_{col}", "interruptions", type_="foreignkey")
            op.drop_column("interruptions", col)

    for name in ("prestataires", "entreprises", "direction_sources", "statuts"):
        if name in set(inspector.get_table_names()):
            op.drop_table(name)
