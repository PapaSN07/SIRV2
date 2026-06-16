from datetime import datetime

from sqlalchemy import (
    DECIMAL,
    NVARCHAR,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.defaults import MSSQL_NOW

# Valid discriminant values
TYPE_DIRECTION_VALUES = ("distribution", "transport", "omvg")
STATUT_VALUES = ("en_cours", "cloture", "valide", "archive")


class Interruption(Base):
    """Table centrale unifiée pour toutes les interruptions réseau.

    Le champ type_direction discrimine la direction (distribution / transport / omvg).
    Les détails métier spécifiques sont dans InterruptionDistribution ou InterruptionTransport.
    """

    __tablename__ = "interruptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    numero_interruption: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    # Discriminant: distribution | transport | omvg
    type_direction: Mapped[str] = mapped_column(NVARCHAR(20), nullable=False, index=True)

    # Statut: en_cours | cloture | valide | archive
    statut: Mapped[str] = mapped_column(
        NVARCHAR(20), nullable=False, default="en_cours", index=True
    )

    # Geo / réseau scope
    service_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("services.id", ondelete="NO ACTION"), nullable=True, index=True
    )
    feeder_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("feeders.id", ondelete="NO ACTION"), nullable=True, index=True
    )
    poste_source_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("postes_sources.id", ondelete="NO ACTION"), nullable=True, index=True
    )

    # Temporal
    date_apparition: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, index=True
    )
    date_remise: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    # Duration in minutes — computed on closure, stored for query performance
    duree_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Characterisation
    cause_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("causes.id", ondelete="NO ACTION"), nullable=True, index=True
    )
    siege_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("sieges.id", ondelete="NO ACTION"), nullable=True, index=True
    )
    signalisation_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("signalisations.id", ondelete="NO ACTION"), nullable=True, index=True
    )
    nature_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("natures.id", ondelete="NO ACTION"), nullable=True, index=True
    )
    is_force_majeure: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_fugitive: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Client impact
    nombre_clients_touches: Mapped[int | None] = mapped_column(Integer, nullable=True)
    puissance_coupee_mw: Mapped[float | None] = mapped_column(DECIMAL(18, 4), nullable=True)

    # Localisation libre
    localisation: Mapped[str | None] = mapped_column(NVARCHAR(500), nullable=True)
    observations: Mapped[str | None] = mapped_column(NVARCHAR(2000), nullable=True)

    # Audit trail
    created_by_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("utilisateurs.id", ondelete="NO ACTION"), nullable=False, index=True
    )
    validated_by_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("utilisateurs.id", ondelete="NO ACTION"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=MSSQL_NOW
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        server_default=MSSQL_NOW,
        onupdate=func.now(),
    )

    __table_args__ = (
        CheckConstraint(
            "type_direction IN ('distribution', 'transport', 'omvg')",
            name="ck_interruption_type_direction",
        ),
        CheckConstraint(
            "statut IN ('en_cours', 'cloture', 'valide', 'archive')",
            name="ck_interruption_statut",
        ),
    )

    # Relationships
    service: Mapped["Service | None"] = relationship("Service", foreign_keys=[service_id], lazy="select")  # noqa: F821
    feeder: Mapped["Feeder | None"] = relationship("Feeder", foreign_keys=[feeder_id], lazy="select")  # noqa: F821
    poste_source: Mapped["PosteSource | None"] = relationship("PosteSource", foreign_keys=[poste_source_id], lazy="select")  # noqa: F821
    cause: Mapped["Cause | None"] = relationship("Cause", foreign_keys=[cause_id], lazy="select")  # noqa: F821
    siege: Mapped["Siege | None"] = relationship("Siege", foreign_keys=[siege_id], lazy="select")  # noqa: F821
    signalisation: Mapped["Signalisation | None"] = relationship("Signalisation", foreign_keys=[signalisation_id], lazy="select")  # noqa: F821
    nature: Mapped["Nature | None"] = relationship("Nature", foreign_keys=[nature_id], lazy="select")  # noqa: F821
    created_by: Mapped["Utilisateur"] = relationship("Utilisateur", foreign_keys=[created_by_id], lazy="select")  # noqa: F821
    validated_by: Mapped["Utilisateur | None"] = relationship("Utilisateur", foreign_keys=[validated_by_id], lazy="select")  # noqa: F821
    interruption_distribution: Mapped["InterruptionDistribution | None"] = relationship(
        "InterruptionDistribution", back_populates="interruption", lazy="select", uselist=False
    )
    interruption_transport: Mapped["InterruptionTransport | None"] = relationship(
        "InterruptionTransport", back_populates="interruption", lazy="select", uselist=False
    )
    postes_interrompus: Mapped[list["PosteInterruption"]] = relationship(
        "PosteInterruption", back_populates="interruption", lazy="select"
    )
    energie_nd: Mapped["EnergieNd | None"] = relationship(  # noqa: F821
        "EnergieNd", back_populates="interruption", lazy="select", uselist=False
    )


class InterruptionDistribution(Base):
    """Détails propres aux interruptions réseau distribution (MT/BT).

    Table-per-type : 1-to-1 avec Interruption (type_direction = 'distribution').
    """

    __tablename__ = "interruptions_distribution"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    interruption_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("interruptions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # MT/BT specific fields
    tension_kv: Mapped[float | None] = mapped_column(DECIMAL(6, 2), nullable=True)
    # Number of MT customers impacted
    nombre_clients_mt: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Number of BT customers impacted
    nombre_clients_bt: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Energie Non Distribuée in MWh — persisted in energie_nd table, mirrored here for reports
    end_mwh: Mapped[float | None] = mapped_column(DECIMAL(18, 4), nullable=True)
    # Planned (délestage) vs unplanned (incident)
    is_programme: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # BT extension — secondary BT fault caused by the MT fault
    has_extension_bt: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Relationships
    interruption: Mapped["Interruption"] = relationship(
        "Interruption", back_populates="interruption_distribution"
    )


class InterruptionTransport(Base):
    """Détails propres aux interruptions réseau transport (HTB).

    Table-per-type : 1-to-1 avec Interruption (type_direction = 'transport' ou 'omvg').
    """

    __tablename__ = "interruptions_transport"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    interruption_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("interruptions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # HTB specific fields
    tension_kv: Mapped[float | None] = mapped_column(DECIMAL(6, 2), nullable=True)
    equipement_transport_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("equipements_transport.id", ondelete="NO ACTION"),
        nullable=True,
        index=True,
    )
    source_transport_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("sources_transport.id", ondelete="NO ACTION"),
        nullable=True,
        index=True,
    )
    puissance_transit_mw: Mapped[float | None] = mapped_column(DECIMAL(18, 4), nullable=True)
    energie_non_fournie_mwh: Mapped[float | None] = mapped_column(DECIMAL(18, 4), nullable=True)

    # Relationships
    interruption: Mapped["Interruption"] = relationship(
        "Interruption", back_populates="interruption_transport"
    )
    equipement_transport: Mapped["EquipementTransport | None"] = relationship(  # noqa: F821
        "EquipementTransport", foreign_keys=[equipement_transport_id], lazy="select"
    )
    source_transport: Mapped["SourceTransport | None"] = relationship(  # noqa: F821
        "SourceTransport", foreign_keys=[source_transport_id], lazy="select"
    )


class PosteInterruption(Base):
    """Table N-N entre interruptions et postes MT/BT impactés."""

    __tablename__ = "poste_interruptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    interruption_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("interruptions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    poste_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("postes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    nombre_clients_touches: Mapped[int | None] = mapped_column(Integer, nullable=True)

    __table_args__ = (
        UniqueConstraint("interruption_id", "poste_id", name="uq_poste_interruption"),
    )

    # Relationships
    interruption: Mapped["Interruption"] = relationship(
        "Interruption", back_populates="postes_interrompus"
    )
    poste: Mapped["Poste"] = relationship("Poste", foreign_keys=[poste_id], lazy="select")  # noqa: F821
