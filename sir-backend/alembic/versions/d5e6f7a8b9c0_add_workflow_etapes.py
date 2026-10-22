"""add etapes_workflow + workflows (chained steps), migrate interruption_workflow_steps

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
Create Date: 2026-10-15 12:45:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d5e6f7a8b9c0"
down_revision: Union[str, None] = "c4d5e6f7a8b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (id, code, libellé, ordre, id étape suivante)
ETAPES = [
    (1, "declenchement", "Déclenchement", 1, 2),
    (2, "interpellation_pdm", "Interpellation PDM", 2, 3),
    (3, "tronconnement", "Tronçonnement", 3, 4),
    (4, "localisation", "Localisation", 4, 5),
    (5, "reparation", "Réparation", 5, 6),
    (6, "remise", "Remise", 6, None),
]

# (id étape, colonne début, colonne fin) dans interruption_workflow_steps
LEGACY_DATES = [
    (1, "date_debut_declenchement", "date_fin_declenchement"),
    (2, "date_interpellation_pdm", "date_arrivee_pdm"),
    (4, "date_debut_localisation", "date_fin_localisation"),
    (5, "date_debut_reparation", "date_fin_reparation"),
    (6, "date_debut_remise", "date_fin_remise"),
]

VIEW_TRONCON_SIG_WORKFLOWS = """
CREATE VIEW dbo.v_ml_incidents_troncon_sig AS
SELECT
    w.troncon_sig_id,
    ts.nom_troncon AS troncon_sig_libelle,
    i.feeder_id,
    i.service_id,
    COUNT(*) AS nb_interruptions,
    AVG(CAST(i.duree_minutes AS FLOAT)) AS duree_moyenne_minutes,
    MAX(i.date_apparition) AS derniere_apparition
FROM dbo.workflows w
INNER JOIN dbo.interruptions i ON i.id = w.interruption_id
LEFT JOIN dbo.troncons_sig ts ON ts.id = w.troncon_sig_id
WHERE i.type_direction = N'distribution'
  AND w.troncon_sig_id IS NOT NULL
GROUP BY w.troncon_sig_id, ts.nom_troncon, i.feeder_id, i.service_id
"""

VIEW_TRONCON_SIG_LEGACY = """
CREATE VIEW dbo.v_ml_incidents_troncon_sig AS
SELECT
    w.troncon_sig_id,
    ts.nom_troncon AS troncon_sig_libelle,
    i.feeder_id,
    i.service_id,
    COUNT(*) AS nb_interruptions,
    AVG(CAST(i.duree_minutes AS FLOAT)) AS duree_moyenne_minutes,
    MAX(i.date_apparition) AS derniere_apparition
FROM dbo.interruption_workflow_steps w
INNER JOIN dbo.interruptions i ON i.id = w.interruption_id
LEFT JOIN dbo.troncons_sig ts ON ts.id = w.troncon_sig_id
WHERE i.type_direction = N'distribution'
  AND w.troncon_sig_id IS NOT NULL
GROUP BY w.troncon_sig_id, ts.nom_troncon, i.feeder_id, i.service_id
"""

DROP_VIEW = (
    "IF OBJECT_ID('dbo.v_ml_incidents_troncon_sig', 'V') IS NOT NULL "
    "DROP VIEW dbo.v_ml_incidents_troncon_sig"
)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "etapes_workflow" not in tables:
        op.create_table(
            "etapes_workflow",
            sa.Column("id", sa.Integer(), autoincrement=False, nullable=False),
            sa.Column("code", sa.NVARCHAR(length=30), nullable=False),
            sa.Column("libelle_etape_workflow", sa.NVARCHAR(length=100), nullable=False),
            sa.Column("ordre", sa.Integer(), nullable=False),
            sa.Column("etape_suivante_id", sa.Integer(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("code", name="uq_etapes_workflow_code"),
            sa.ForeignKeyConstraint(
                ["etape_suivante_id"],
                ["etapes_workflow.id"],
                name="fk_etapes_workflow_etape_suivante_id",
            ),
        )

    # Insertion en ordre inverse pour respecter l'auto-référence
    for eid, code, libelle, ordre, suivante in reversed(ETAPES):
        op.execute(
            sa.text(
                "IF NOT EXISTS (SELECT 1 FROM dbo.etapes_workflow WHERE id = :id) "
                "INSERT INTO dbo.etapes_workflow (id, code, libelle_etape_workflow, ordre, etape_suivante_id) "
                "VALUES (:id, :code, :libelle, :ordre, :suivante)"
            ).bindparams(id=eid, code=code, libelle=libelle, ordre=ordre, suivante=suivante)
        )

    if "workflows" not in tables:
        op.create_table(
            "workflows",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("interruption_id", sa.Integer(), nullable=False),
            sa.Column("etape_workflow_id", sa.Integer(), nullable=False),
            sa.Column("date_debut", sa.DateTime(), nullable=True),
            sa.Column("date_fin", sa.DateTime(), nullable=True),
            sa.Column("observation", sa.NVARCHAR(length=2000), nullable=True),
            sa.Column("troncon_id", sa.Integer(), nullable=True),
            sa.Column("troncon_sig_id", sa.Integer(), nullable=True),
            sa.Column("noeud_amont_libelle", sa.NVARCHAR(length=255), nullable=True),
            sa.Column("noeud_aval_libelle", sa.NVARCHAR(length=255), nullable=True),
            sa.Column("responsable_matricule", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.text("(getdate())"), nullable=False),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(getdate())"), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "interruption_id", "etape_workflow_id", name="uq_workflow_interruption_etape"
            ),
            sa.CheckConstraint(
                "date_fin IS NULL OR date_debut IS NULL OR date_fin >= date_debut",
                name="ck_workflow_dates",
            ),
            sa.ForeignKeyConstraint(
                ["interruption_id"], ["interruptions.id"],
                name="fk_workflows_interruption_id", ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["etape_workflow_id"], ["etapes_workflow.id"], name="fk_workflows_etape_workflow_id"
            ),
            sa.ForeignKeyConstraint(["troncon_id"], ["troncons.id"], name="fk_workflows_troncon_id"),
            sa.ForeignKeyConstraint(
                ["troncon_sig_id"], ["troncons_sig.id"], name="fk_workflows_troncon_sig_id"
            ),
        )
        for col in ("interruption_id", "etape_workflow_id", "troncon_id", "troncon_sig_id"):
            op.create_index(f"ix_workflows_{col}", "workflows", [col])

    if "interruption_workflow_steps" in tables:
        _migrate_legacy_rows()

    op.execute(sa.text(DROP_VIEW))
    op.execute(sa.text(VIEW_TRONCON_SIG_WORKFLOWS))


def _migrate_legacy_rows() -> None:
    """Copie idempotente : une ligne `workflows` par étape renseignée.

    Les dates hors fenêtre (fin < début) sont copiées sans la fin pour respecter
    la contrainte ck_workflow_dates.
    """
    for etape_id, col_debut, col_fin in LEGACY_DATES:
        op.execute(
            sa.text(
                f"""
                INSERT INTO dbo.workflows (interruption_id, etape_workflow_id, date_debut, date_fin)
                SELECT s.interruption_id, {etape_id}, s.{col_debut},
                       CASE WHEN s.{col_debut} IS NOT NULL AND s.{col_fin} < s.{col_debut}
                            THEN NULL ELSE s.{col_fin} END
                FROM dbo.interruption_workflow_steps AS s
                WHERE (s.{col_debut} IS NOT NULL OR s.{col_fin} IS NOT NULL)
                  AND NOT EXISTS (
                      SELECT 1 FROM dbo.workflows w
                      WHERE w.interruption_id = s.interruption_id AND w.etape_workflow_id = {etape_id}
                  )
                """
            )
        )

    op.execute(
        sa.text(
            """
            INSERT INTO dbo.workflows (
                interruption_id, etape_workflow_id, date_debut, date_fin,
                troncon_id, troncon_sig_id, noeud_amont_libelle, noeud_aval_libelle
            )
            SELECT s.interruption_id, 3, s.date_debut_tronconnement,
                   CASE WHEN s.date_debut_tronconnement IS NOT NULL
                             AND s.date_fin_tronconnement < s.date_debut_tronconnement
                        THEN NULL ELSE s.date_fin_tronconnement END,
                   s.troncon_id, s.troncon_sig_id, s.noeud_amont_libelle, s.noeud_aval_libelle
            FROM dbo.interruption_workflow_steps AS s
            WHERE (s.date_debut_tronconnement IS NOT NULL OR s.date_fin_tronconnement IS NOT NULL
                   OR s.troncon_id IS NOT NULL OR s.troncon_sig_id IS NOT NULL
                   OR s.noeud_amont_libelle IS NOT NULL OR s.noeud_aval_libelle IS NOT NULL)
              AND NOT EXISTS (
                  SELECT 1 FROM dbo.workflows w
                  WHERE w.interruption_id = s.interruption_id AND w.etape_workflow_id = 3
              )
            """
        )
    )

    # Observation / responsable sans aucune étape datée : rattachés au déclenchement
    op.execute(
        sa.text(
            """
            INSERT INTO dbo.workflows (interruption_id, etape_workflow_id)
            SELECT s.interruption_id, 1
            FROM dbo.interruption_workflow_steps AS s
            WHERE (s.observations_workflow IS NOT NULL OR s.responsable_matricule IS NOT NULL)
              AND NOT EXISTS (SELECT 1 FROM dbo.workflows w WHERE w.interruption_id = s.interruption_id)
            """
        )
    )

    op.execute(
        sa.text(
            """
            UPDATE w
            SET observation = COALESCE(w.observation, s.observations_workflow),
                responsable_matricule = COALESCE(w.responsable_matricule, s.responsable_matricule)
            FROM dbo.workflows AS w
            INNER JOIN dbo.interruption_workflow_steps AS s ON s.interruption_id = w.interruption_id
            INNER JOIN dbo.etapes_workflow AS e ON e.id = w.etape_workflow_id
            WHERE e.ordre = (
                SELECT MAX(e2.ordre)
                FROM dbo.workflows w2
                INNER JOIN dbo.etapes_workflow e2 ON e2.id = w2.etape_workflow_id
                WHERE w2.interruption_id = w.interruption_id
            )
            AND (s.observations_workflow IS NOT NULL OR s.responsable_matricule IS NOT NULL)
            """
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    op.execute(sa.text(DROP_VIEW))
    if "interruption_workflow_steps" in tables:
        op.execute(sa.text(VIEW_TRONCON_SIG_LEGACY))

    if "workflows" in tables:
        op.drop_table("workflows")
    if "etapes_workflow" in tables:
        op.drop_table("etapes_workflow")
