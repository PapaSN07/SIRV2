"""Modèles Assistant ML — prédictions risque / conversations (module satellite)."""

from datetime import datetime

from sqlalchemy import (
    DECIMAL,
    NVARCHAR,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.defaults import MSSQL_NOW


class MlFeatureSnapshot(Base):
    """Snapshot de features agrégées (feeder / tronçon SIG / poste) pour scoring."""

    __tablename__ = "ml_feature_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entity_type: Mapped[str] = mapped_column(NVARCHAR(20), nullable=False, index=True)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    horizon_days: Mapped[int] = mapped_column(Integer, nullable=False, default=90)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    nb_interruptions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    nb_permanentes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duree_moyenne_minutes: Mapped[float | None] = mapped_column(DECIMAL(18, 4), nullable=True)
    clients_touches_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    service_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("services.id", ondelete="NO ACTION"), nullable=True, index=True
    )
    feeder_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("feeders.id", ondelete="NO ACTION"), nullable=True, index=True
    )
    features_json: Mapped[str | None] = mapped_column(NVARCHAR(4000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=MSSQL_NOW
    )

    __table_args__ = (
        UniqueConstraint(
            "entity_type",
            "entity_id",
            "horizon_days",
            "window_end",
            name="uq_ml_feature_snapshot_entity_window",
        ),
    )


class MlPrediction(Base):
    """Score de risque panne / travaux (P0 règles, puis P1+ modèles)."""

    __tablename__ = "ml_predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entity_type: Mapped[str] = mapped_column(NVARCHAR(20), nullable=False, index=True)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    entity_libelle: Mapped[str | None] = mapped_column(NVARCHAR(255), nullable=True)
    horizon_days: Mapped[int] = mapped_column(Integer, nullable=False, default=90)
    risk_score: Mapped[float] = mapped_column(DECIMAL(8, 4), nullable=False)
    risk_level: Mapped[str] = mapped_column(NVARCHAR(20), nullable=False, index=True)
    model_version: Mapped[str] = mapped_column(NVARCHAR(50), nullable=False, default="p0-rules-v1")
    factors_json: Mapped[str | None] = mapped_column(NVARCHAR(4000), nullable=True)
    recommendation: Mapped[str | None] = mapped_column(NVARCHAR(1000), nullable=True)
    service_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("services.id", ondelete="NO ACTION"), nullable=True, index=True
    )
    feeder_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("feeders.id", ondelete="NO ACTION"), nullable=True, index=True
    )
    feature_snapshot_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("ml_feature_snapshots.id", ondelete="NO ACTION"),
        nullable=True,
        index=True,
    )
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=MSSQL_NOW
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    feature_snapshot: Mapped["MlFeatureSnapshot | None"] = relationship(
        "MlFeatureSnapshot", foreign_keys=[feature_snapshot_id], lazy="select"
    )


class AssistantConversation(Base):
    """Audit des échanges Assistant (suggestions, pas de décision métier)."""

    __tablename__ = "assistant_conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("utilisateurs.id", ondelete="NO ACTION"), nullable=False, index=True
    )
    question: Mapped[str] = mapped_column(NVARCHAR(2000), nullable=False)
    answer: Mapped[str] = mapped_column(NVARCHAR(4000), nullable=False)
    context_json: Mapped[str | None] = mapped_column(NVARCHAR(2000), nullable=True)
    feeder_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("feeders.id", ondelete="NO ACTION"), nullable=True, index=True
    )
    interruption_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("interruptions.id", ondelete="NO ACTION"), nullable=True, index=True
    )
    accepted: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        server_default=MSSQL_NOW,
        index=True,
    )

    user: Mapped["Utilisateur"] = relationship(  # noqa: F821
        "Utilisateur", foreign_keys=[user_id], lazy="select"
    )
