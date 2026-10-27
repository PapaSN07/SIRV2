"""Historique des changements de statut d'une interruption (frise de la fiche, délais, alertes)."""

from datetime import datetime

from sqlalchemy import NVARCHAR, CheckConstraint, DateTime, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.defaults import MSSQL_NOW

ACTION_CREATION = "creation"
ACTION_CLOTURE = "cloture"
ACTION_VALIDATION = "validation"
ACTION_RENVOI = "renvoi_correction"
ACTION_DEVALIDATION = "devalidation"
ACTION_ARCHIVAGE = "archivage"
ACTIONS_STATUT = (
    ACTION_CREATION,
    ACTION_CLOTURE,
    ACTION_VALIDATION,
    ACTION_RENVOI,
    ACTION_DEVALIDATION,
    ACTION_ARCHIVAGE,
)


class InterruptionStatutHistorique(Base):
    __tablename__ = "interruption_statuts_historique"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    interruption_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("interruptions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    action: Mapped[str] = mapped_column(NVARCHAR(30), nullable=False)
    ancien_statut: Mapped[str | None] = mapped_column(NVARCHAR(20), nullable=True)
    nouveau_statut: Mapped[str] = mapped_column(NVARCHAR(20), nullable=False)
    motif: Mapped[str | None] = mapped_column(NVARCHAR(1000), nullable=True)
    utilisateur_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("utilisateurs.id", ondelete="NO ACTION"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=MSSQL_NOW, index=True
    )

    utilisateur: Mapped["Utilisateur"] = relationship("Utilisateur", lazy="select")  # noqa: F821

    __table_args__ = (
        CheckConstraint(
            "action IN ('creation', 'cloture', 'validation', 'renvoi_correction', "
            "'devalidation', 'archivage')",
            name="ck_interruption_statut_histo_action",
        ),
    )
