"""add assistant ML tables + datamart views

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-09-22 12:55:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "ml_feature_snapshots" not in tables:
        op.create_table(
            "ml_feature_snapshots",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("entity_type", sa.NVARCHAR(length=20), nullable=False),
            sa.Column("entity_id", sa.Integer(), nullable=False),
            sa.Column("horizon_days", sa.Integer(), nullable=False),
            sa.Column("window_start", sa.DateTime(), nullable=False),
            sa.Column("window_end", sa.DateTime(), nullable=False),
            sa.Column("nb_interruptions", sa.Integer(), nullable=False),
            sa.Column("nb_permanentes", sa.Integer(), nullable=False),
            sa.Column("duree_moyenne_minutes", sa.DECIMAL(18, 4), nullable=True),
            sa.Column("clients_touches_total", sa.Integer(), nullable=False),
            sa.Column("service_id", sa.Integer(), nullable=True),
            sa.Column("feeder_id", sa.Integer(), nullable=True),
            sa.Column("features_json", sa.NVARCHAR(length=4000), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(),
                server_default=sa.text("(getdate())"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(
                ["service_id"], ["services.id"], name="fk_ml_feature_snapshots_service_id"
            ),
            sa.ForeignKeyConstraint(
                ["feeder_id"], ["feeders.id"], name="fk_ml_feature_snapshots_feeder_id"
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "entity_type",
                "entity_id",
                "horizon_days",
                "window_end",
                name="uq_ml_feature_snapshot_entity_window",
            ),
        )
        op.create_index(
            "ix_ml_feature_snapshots_entity_type",
            "ml_feature_snapshots",
            ["entity_type"],
        )
        op.create_index(
            "ix_ml_feature_snapshots_entity_id",
            "ml_feature_snapshots",
            ["entity_id"],
        )
        op.create_index(
            "ix_ml_feature_snapshots_service_id",
            "ml_feature_snapshots",
            ["service_id"],
        )
        op.create_index(
            "ix_ml_feature_snapshots_feeder_id",
            "ml_feature_snapshots",
            ["feeder_id"],
        )

    if "ml_predictions" not in tables:
        op.create_table(
            "ml_predictions",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("entity_type", sa.NVARCHAR(length=20), nullable=False),
            sa.Column("entity_id", sa.Integer(), nullable=False),
            sa.Column("entity_libelle", sa.NVARCHAR(length=255), nullable=True),
            sa.Column("horizon_days", sa.Integer(), nullable=False),
            sa.Column("risk_score", sa.DECIMAL(8, 4), nullable=False),
            sa.Column("risk_level", sa.NVARCHAR(length=20), nullable=False),
            sa.Column("model_version", sa.NVARCHAR(length=50), nullable=False),
            sa.Column("factors_json", sa.NVARCHAR(length=4000), nullable=True),
            sa.Column("recommendation", sa.NVARCHAR(length=1000), nullable=True),
            sa.Column("service_id", sa.Integer(), nullable=True),
            sa.Column("feeder_id", sa.Integer(), nullable=True),
            sa.Column("feature_snapshot_id", sa.Integer(), nullable=True),
            sa.Column(
                "calculated_at",
                sa.DateTime(),
                server_default=sa.text("(getdate())"),
                nullable=False,
            ),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            sa.ForeignKeyConstraint(
                ["service_id"], ["services.id"], name="fk_ml_predictions_service_id"
            ),
            sa.ForeignKeyConstraint(
                ["feeder_id"], ["feeders.id"], name="fk_ml_predictions_feeder_id"
            ),
            sa.ForeignKeyConstraint(
                ["feature_snapshot_id"],
                ["ml_feature_snapshots.id"],
                name="fk_ml_predictions_feature_snapshot_id",
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_ml_predictions_entity_type", "ml_predictions", ["entity_type"])
        op.create_index("ix_ml_predictions_entity_id", "ml_predictions", ["entity_id"])
        op.create_index("ix_ml_predictions_risk_level", "ml_predictions", ["risk_level"])
        op.create_index("ix_ml_predictions_service_id", "ml_predictions", ["service_id"])
        op.create_index("ix_ml_predictions_feeder_id", "ml_predictions", ["feeder_id"])
        op.create_index(
            "ix_ml_predictions_feature_snapshot_id",
            "ml_predictions",
            ["feature_snapshot_id"],
        )

    if "assistant_conversations" not in tables:
        op.create_table(
            "assistant_conversations",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("question", sa.NVARCHAR(length=2000), nullable=False),
            sa.Column("answer", sa.NVARCHAR(length=4000), nullable=False),
            sa.Column("context_json", sa.NVARCHAR(length=2000), nullable=True),
            sa.Column("feeder_id", sa.Integer(), nullable=True),
            sa.Column("interruption_id", sa.Integer(), nullable=True),
            sa.Column("accepted", sa.Boolean(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(),
                server_default=sa.text("(getdate())"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(
                ["user_id"], ["utilisateurs.id"], name="fk_assistant_conversations_user_id"
            ),
            sa.ForeignKeyConstraint(
                ["feeder_id"], ["feeders.id"], name="fk_assistant_conversations_feeder_id"
            ),
            sa.ForeignKeyConstraint(
                ["interruption_id"],
                ["interruptions.id"],
                name="fk_assistant_conversations_interruption_id",
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_assistant_conversations_user_id", "assistant_conversations", ["user_id"]
        )
        op.create_index(
            "ix_assistant_conversations_feeder_id",
            "assistant_conversations",
            ["feeder_id"],
        )
        op.create_index(
            "ix_assistant_conversations_interruption_id",
            "assistant_conversations",
            ["interruption_id"],
        )
        op.create_index(
            "ix_assistant_conversations_created_at",
            "assistant_conversations",
            ["created_at"],
        )

    # Datamart lecture seule — agrégats incidents
    op.execute(sa.text("IF OBJECT_ID('dbo.v_ml_incidents_feeder_mois', 'V') IS NOT NULL DROP VIEW dbo.v_ml_incidents_feeder_mois"))
    op.execute(
        sa.text(
            """
            CREATE VIEW dbo.v_ml_incidents_feeder_mois AS
            SELECT
                i.feeder_id,
                f.code AS feeder_code,
                f.libelle AS feeder_libelle,
                i.service_id,
                YEAR(i.date_apparition) AS annee,
                MONTH(i.date_apparition) AS mois,
                COUNT(*) AS nb_interruptions,
                SUM(CASE WHEN i.is_force_majeure = 1 THEN 1 ELSE 0 END) AS nb_force_majeure,
                AVG(CAST(i.duree_minutes AS FLOAT)) AS duree_moyenne_minutes,
                SUM(COALESCE(i.nombre_clients_touches, 0)) AS clients_touches_total
            FROM dbo.interruptions i
            LEFT JOIN dbo.feeders f ON f.id = i.feeder_id
            WHERE i.type_direction = N'distribution'
              AND i.feeder_id IS NOT NULL
            GROUP BY
                i.feeder_id,
                f.code,
                f.libelle,
                i.service_id,
                YEAR(i.date_apparition),
                MONTH(i.date_apparition)
            """
        )
    )

    op.execute(sa.text("IF OBJECT_ID('dbo.v_ml_incidents_troncon_sig', 'V') IS NOT NULL DROP VIEW dbo.v_ml_incidents_troncon_sig"))
    op.execute(
        sa.text(
            """
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
            GROUP BY
                w.troncon_sig_id,
                ts.nom_troncon,
                i.feeder_id,
                i.service_id
            """
        )
    )

    op.execute(sa.text("IF OBJECT_ID('dbo.v_ml_incidents_poste', 'V') IS NOT NULL DROP VIEW dbo.v_ml_incidents_poste"))
    op.execute(
        sa.text(
            """
            CREATE VIEW dbo.v_ml_incidents_poste AS
            SELECT
                pi.poste_id,
                p.code AS poste_code,
                p.libelle AS poste_libelle,
                COALESCE(pi.feeder_id, p.feeder_id) AS feeder_id,
                COALESCE(pi.service_id, p.service_id) AS service_id,
                COUNT(*) AS nb_impactes,
                SUM(COALESCE(pi.nombre_clients_touches, 0)) AS clients_touches_total,
                MAX(i.date_apparition) AS derniere_apparition
            FROM dbo.poste_interruptions pi
            INNER JOIN dbo.interruptions i ON i.id = pi.interruption_id
            LEFT JOIN dbo.postes p ON p.id = pi.poste_id
            WHERE i.type_direction = N'distribution'
            GROUP BY
                pi.poste_id,
                p.code,
                p.libelle,
                COALESCE(pi.feeder_id, p.feeder_id),
                COALESCE(pi.service_id, p.service_id)
            """
        )
    )


def downgrade() -> None:
    op.execute(sa.text("IF OBJECT_ID('dbo.v_ml_incidents_poste', 'V') IS NOT NULL DROP VIEW dbo.v_ml_incidents_poste"))
    op.execute(sa.text("IF OBJECT_ID('dbo.v_ml_incidents_troncon_sig', 'V') IS NOT NULL DROP VIEW dbo.v_ml_incidents_troncon_sig"))
    op.execute(sa.text("IF OBJECT_ID('dbo.v_ml_incidents_feeder_mois', 'V') IS NOT NULL DROP VIEW dbo.v_ml_incidents_feeder_mois"))

    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "assistant_conversations" in tables:
        op.drop_table("assistant_conversations")
    if "ml_predictions" in tables:
        op.drop_table("ml_predictions")
    if "ml_feature_snapshots" in tables:
        op.drop_table("ml_feature_snapshots")
