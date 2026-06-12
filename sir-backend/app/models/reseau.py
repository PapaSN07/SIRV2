from sqlalchemy import DECIMAL, NVARCHAR, Boolean, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class PosteSource(Base):
    """Poste de transformation HTB/MT (point d'injection dans le réseau distribution)."""

    __tablename__ = "postes_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(NVARCHAR(20), nullable=False, unique=True)
    libelle: Mapped[str] = mapped_column(NVARCHAR(200), nullable=False)
    region_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("regions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    puissance_mva: Mapped[float | None] = mapped_column(DECIMAL(10, 2), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Relationships
    region: Mapped["Region | None"] = relationship("Region", foreign_keys=[region_id], lazy="select")  # noqa: F821
    feeders: Mapped[list["Feeder"]] = relationship(
        "Feeder", back_populates="poste_source", lazy="select"
    )


class Feeder(Base):
    """Départ MT depuis un poste source."""

    __tablename__ = "feeders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    poste_source_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("postes_sources.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    service_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("services.id", ondelete="SET NULL"), nullable=True, index=True
    )
    code: Mapped[str] = mapped_column(NVARCHAR(20), nullable=False, unique=True)
    libelle: Mapped[str] = mapped_column(NVARCHAR(200), nullable=False)
    tension_kv: Mapped[float | None] = mapped_column(DECIMAL(6, 2), nullable=True)
    puissance_installee_mva: Mapped[float | None] = mapped_column(DECIMAL(10, 2), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Relationships
    poste_source: Mapped["PosteSource"] = relationship(
        "PosteSource", back_populates="feeders"
    )
    service: Mapped["Service | None"] = relationship("Service", foreign_keys=[service_id], lazy="select")  # noqa: F821
    sous_feeders: Mapped[list["SousFeeder"]] = relationship(
        "SousFeeder", back_populates="feeder", lazy="select"
    )


class SousFeeder(Base):
    """Subdivision d'un feeder MT."""

    __tablename__ = "sous_feeders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    feeder_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("feeders.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(NVARCHAR(20), nullable=False, unique=True)
    libelle: Mapped[str] = mapped_column(NVARCHAR(200), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Relationships
    feeder: Mapped["Feeder"] = relationship("Feeder", back_populates="sous_feeders")


class Poste(Base):
    """Poste de transformation MT/BT (côté distribution)."""

    __tablename__ = "postes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    feeder_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("feeders.id", ondelete="SET NULL"), nullable=True, index=True
    )
    service_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("services.id", ondelete="SET NULL"), nullable=True, index=True
    )
    code: Mapped[str] = mapped_column(NVARCHAR(20), nullable=False, unique=True)
    libelle: Mapped[str] = mapped_column(NVARCHAR(200), nullable=False)
    puissance_kva: Mapped[float | None] = mapped_column(DECIMAL(10, 2), nullable=True)
    nombre_clients: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Relationships
    feeder: Mapped["Feeder | None"] = relationship("Feeder", foreign_keys=[feeder_id], lazy="select")
    service: Mapped["Service | None"] = relationship("Service", foreign_keys=[service_id], lazy="select")  # noqa: F821


class Troncon(Base):
    """Section de ligne entre deux noeuds du réseau."""

    __tablename__ = "troncons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    feeder_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("feeders.id", ondelete="SET NULL"), nullable=True, index=True
    )
    code: Mapped[str] = mapped_column(NVARCHAR(20), nullable=False, unique=True)
    libelle: Mapped[str] = mapped_column(NVARCHAR(200), nullable=False)
    longueur_km: Mapped[float | None] = mapped_column(DECIMAL(10, 3), nullable=True)
    tension_kv: Mapped[float | None] = mapped_column(DECIMAL(6, 2), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Relationships
    feeder: Mapped["Feeder | None"] = relationship("Feeder", foreign_keys=[feeder_id], lazy="select")


class EquipementTransport(Base):
    """Equipement du réseau HTB (transport)."""

    __tablename__ = "equipements_transport"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(NVARCHAR(20), nullable=False, unique=True)
    libelle: Mapped[str] = mapped_column(NVARCHAR(200), nullable=False)
    type_equipement: Mapped[str] = mapped_column(NVARCHAR(50), nullable=False)
    tension_kv: Mapped[float | None] = mapped_column(DECIMAL(6, 2), nullable=True)
    puissance_mva: Mapped[float | None] = mapped_column(DECIMAL(10, 2), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class SourceTransport(Base):
    """Source d'alimentation du réseau transport (groupe, interconnexion…)."""

    __tablename__ = "sources_transport"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(NVARCHAR(20), nullable=False, unique=True)
    libelle: Mapped[str] = mapped_column(NVARCHAR(200), nullable=False)
    puissance_mw: Mapped[float | None] = mapped_column(DECIMAL(10, 2), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class PosteLigne(Base):
    """Association entre un poste source et une ligne HTB (réseau transport)."""

    __tablename__ = "postes_lignes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    poste_source_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("postes_sources.id", ondelete="CASCADE"), nullable=False, index=True
    )
    equipement_transport_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("equipements_transport.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Relationships
    poste_source: Mapped["PosteSource"] = relationship(
        "PosteSource", foreign_keys=[poste_source_id], lazy="select"
    )
    equipement_transport: Mapped["EquipementTransport"] = relationship(
        "EquipementTransport", foreign_keys=[equipement_transport_id], lazy="select"
    )
