from datetime import datetime

from sqlalchemy import NVARCHAR, Boolean, CheckConstraint, DateTime, ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

NAPT_STATUT_VALUES = ("brouillon", "soumis", "approuve", "rejete", "archive")
CONSIGNATION_STATUT_VALUES = ("ouverte", "levee", "annulee")


class Napt(Base):
    """Note d'Autorisation de Procéder aux Travaux."""

    __tablename__ = "napt"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    numero_napt: Mapped[str] = mapped_column(NVARCHAR(50), nullable=False, unique=True)
    service_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("services.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    feeder_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("feeders.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    statut: Mapped[str] = mapped_column(
        NVARCHAR(20), nullable=False, default="brouillon", index=True
    )
    objet_travaux: Mapped[str] = mapped_column(NVARCHAR(1000), nullable=False)
    date_debut_prevue: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False
    )
    date_fin_prevue: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False
    )
    date_debut_reelle: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    date_fin_reelle: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    is_interruption_necessaire: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    observations: Mapped[str | None] = mapped_column(NVARCHAR(2000), nullable=True)

    # Audit trail
    created_by_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("utilisateurs.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    approved_by_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("utilisateurs.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        CheckConstraint(
            "statut IN ('brouillon', 'soumis', 'approuve', 'rejete', 'archive')",
            name="ck_napt_statut",
        ),
    )

    # Relationships
    service: Mapped["Service"] = relationship("Service", foreign_keys=[service_id], lazy="select")  # noqa: F821
    feeder: Mapped["Feeder | None"] = relationship("Feeder", foreign_keys=[feeder_id], lazy="select")  # noqa: F821
    created_by: Mapped["Utilisateur"] = relationship("Utilisateur", foreign_keys=[created_by_id], lazy="select")  # noqa: F821
    approved_by: Mapped["Utilisateur | None"] = relationship("Utilisateur", foreign_keys=[approved_by_id], lazy="select")  # noqa: F821
    consignations: Mapped[list["Consignation"]] = relationship(
        "Consignation", back_populates="napt", lazy="select"
    )


class Consignation(Base):
    """Consignation électrique associée à un NAPT."""

    __tablename__ = "consignations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    napt_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("napt.id", ondelete="CASCADE"), nullable=False, index=True
    )
    numero_consignation: Mapped[str] = mapped_column(NVARCHAR(50), nullable=False, unique=True)
    statut: Mapped[str] = mapped_column(
        NVARCHAR(20), nullable=False, default="ouverte", index=True
    )
    date_ouverture: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    date_levee: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    agent_consignateur_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("utilisateurs.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    observations: Mapped[str | None] = mapped_column(NVARCHAR(2000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "statut IN ('ouverte', 'levee', 'annulee')",
            name="ck_consignation_statut",
        ),
    )

    # Relationships
    napt: Mapped["Napt"] = relationship("Napt", back_populates="consignations")
    agent_consignateur: Mapped["Utilisateur"] = relationship(  # noqa: F821
        "Utilisateur", foreign_keys=[agent_consignateur_id], lazy="select"
    )
