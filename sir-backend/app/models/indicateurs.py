from datetime import datetime

from sqlalchemy import DECIMAL, Boolean, DateTime, ForeignKey, Integer, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class EnergieNd(Base):
    """Résultats de calcul END (Énergie Non Distribuée) persistés par interruption.

    END (MWh) = Puissance_Coupée (MW) × Durée_Interruption (h)
    Les interruptions force_majeure sont exclues du calcul imputable.
    # TODO(CRSE): les formules exactes de pondération CRSE doivent être validées
    # avec l'équipe SENELEC avant toute mise en production.
    """

    __tablename__ = "energie_nd"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    interruption_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("interruptions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    type_end_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("types_end.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    valeur_mwh: Mapped[float] = mapped_column(DECIMAL(18, 4), nullable=False)
    puissance_coupee_mw: Mapped[float] = mapped_column(DECIMAL(18, 4), nullable=False)
    duree_heures: Mapped[float] = mapped_column(DECIMAL(10, 4), nullable=False)
    # If True, this END is excluded from the imputable total
    est_force_majeure: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=func.now()
    )

    # Relationships
    interruption: Mapped["Interruption"] = relationship("Interruption", back_populates="energie_nd")  # noqa: F821
    type_end: Mapped["TypeEnd | None"] = relationship("TypeEnd", foreign_keys=[type_end_id], lazy="select")  # noqa: F821


class SaifiSaidi(Base):
    """Résultats agrégés SAIFI/SAIDI par service et période (mois/année).

    SAIFI = Σ(clients_interrompus) / total_clients_reference
    SAIDI = Σ(clients_interrompus × durée_minutes) / total_clients_reference
    # TODO(CRSE): les pondérations exactes doivent être confirmées avec SENELEC.
    """

    __tablename__ = "saifi_saidi"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    service_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("services.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    annee: Mapped[int] = mapped_column(Integer, nullable=False)
    mois: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-12
    saifi: Mapped[float] = mapped_column(DECIMAL(18, 6), nullable=False)
    saidi: Mapped[float] = mapped_column(DECIMAL(18, 6), nullable=False)
    nombre_interruptions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_clients_reference: Mapped[int] = mapped_column(Integer, nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("service_id", "annee", "mois", name="uq_saifi_saidi_service_periode"),
    )

    # Relationships
    service: Mapped["Service"] = relationship("Service", foreign_keys=[service_id], lazy="select")  # noqa: F821


class NombreClientMois(Base):
    """Snapshot mensuel du nombre de clients par service.

    Utilisé comme dénominateur pour SAIFI/SAIDI.
    Alimenté par import mensuel ou saisie manuelle.
    """

    __tablename__ = "nombre_client_mois"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    service_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("services.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    annee: Mapped[int] = mapped_column(Integer, nullable=False)
    mois: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-12
    nombre_clients: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint(
            "service_id", "annee", "mois", name="uq_nombre_client_mois_service_periode"
        ),
    )

    # Relationships
    service: Mapped["Service"] = relationship("Service", foreign_keys=[service_id], lazy="select")  # noqa: F821
