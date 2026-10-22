"""Données topologie SIG importées depuis HFSQL (Troncon_SIG, Noeud_SIG)."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, NVARCHAR, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import DECIMAL, Float

from app.core.database import Base
from app.models.defaults import MSSQL_NOW


class NoeudSig(Base):
    """Nœud réseau SIG (poste, piquage, etc.)."""

    __tablename__ = "noeuds_sig"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    legacy_id: Mapped[int] = mapped_column(Integer, nullable=False, unique=True, index=True)
    legacy_fid: Mapped[int] = mapped_column(Integer, nullable=False, unique=True, index=True)
    nom: Mapped[str | None] = mapped_column(NVARCHAR(255), nullable=True, index=True)
    nom_feeder: Mapped[str | None] = mapped_column(NVARCHAR(255), nullable=True, index=True)
    feeder_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("feeders.id", ondelete="NO ACTION"), nullable=True, index=True
    )
    station: Mapped[str | None] = mapped_column(NVARCHAR(255), nullable=True)
    coord_x: Mapped[float | None] = mapped_column(Float, nullable=True)
    coord_y: Mapped[float | None] = mapped_column(Float, nullable=True)
    categorie: Mapped[str | None] = mapped_column(NVARCHAR(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=MSSQL_NOW
    )

    feeder: Mapped["Feeder | None"] = relationship("Feeder", lazy="select")  # noqa: F821


class TronconSig(Base):
    """Tronçon SIG entre deux nœuds (ligne MT)."""

    __tablename__ = "troncons_sig"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    legacy_id: Mapped[int] = mapped_column(Integer, nullable=False, unique=True, index=True)
    legacy_fid: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    nom_feeder: Mapped[str | None] = mapped_column(NVARCHAR(255), nullable=True, index=True)
    feeder_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("feeders.id", ondelete="NO ACTION"), nullable=True, index=True
    )
    nom_troncon: Mapped[str | None] = mapped_column(NVARCHAR(255), nullable=True)
    nom_noeud_amont: Mapped[str | None] = mapped_column(NVARCHAR(255), nullable=True, index=True)
    code_noeud_amont: Mapped[str | None] = mapped_column(NVARCHAR(100), nullable=True, index=True)
    nom_noeud_aval: Mapped[str | None] = mapped_column(NVARCHAR(255), nullable=True, index=True)
    code_noeud_aval: Mapped[str | None] = mapped_column(NVARCHAR(100), nullable=True, index=True)
    tension_kv: Mapped[float | None] = mapped_column(DECIMAL(6, 2), nullable=True)
    longueur_m: Mapped[float | None] = mapped_column(DECIMAL(12, 3), nullable=True)
    date_chargement: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=MSSQL_NOW
    )

    feeder: Mapped["Feeder | None"] = relationship("Feeder", lazy="select")  # noqa: F821
    workflows: Mapped[list["Workflow"]] = relationship(  # noqa: F821
        "Workflow", back_populates="troncon_sig", lazy="select"
    )

    __table_args__ = (
        UniqueConstraint("legacy_fid", "date_chargement", name="uq_troncons_sig_fid_chargement"),
    )
