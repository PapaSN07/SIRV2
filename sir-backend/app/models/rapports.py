"""Modèle — rapports générés (Sprint 6.6)."""

from datetime import datetime

from sqlalchemy import NVARCHAR, DateTime, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.defaults import MSSQL_NOW

RAPPORT_STATUT_VALUES = ("pending", "started", "success", "failure")
RAPPORT_FORMAT_VALUES = ("pdf", "xlsx")
RAPPORT_TYPE_VALUES = (
    "journalier",
    "mensuel_distribution",
    "mensuel_transport",
    "annuel",
)


class RapportGenere(Base):
    """Suivi d'une génération de rapport CRSE (job Celery + fichier produit)."""

    __tablename__ = "rapports_generes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(NVARCHAR(64), nullable=False, unique=True, index=True)
    type_rapport: Mapped[str] = mapped_column(NVARCHAR(40), nullable=False, index=True)
    format: Mapped[str] = mapped_column(NVARCHAR(10), nullable=False)
    statut: Mapped[str] = mapped_column(NVARCHAR(20), nullable=False, default="pending", index=True)
    file_path: Mapped[str | None] = mapped_column(NVARCHAR(500), nullable=True)
    file_name: Mapped[str | None] = mapped_column(NVARCHAR(255), nullable=True)
    error_message: Mapped[str | None] = mapped_column(NVARCHAR(2000), nullable=True)
    params_json: Mapped[str | None] = mapped_column(NVARCHAR(4000), nullable=True)
    region_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("utilisateurs.id", ondelete="NO ACTION"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=MSSQL_NOW
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=MSSQL_NOW
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)

    user: Mapped["Utilisateur"] = relationship("Utilisateur", foreign_keys=[user_id], lazy="select")  # noqa: F821
