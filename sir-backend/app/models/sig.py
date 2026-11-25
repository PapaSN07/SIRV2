"""Données topologie SIG importées depuis HFSQL (PosteSource_SIG, FEEDERS_SIG, Troncon_SIG, Noeud_SIG)."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, NVARCHAR, UniqueConstraint
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
    # Colonnes complémentaires de Noeud_SIG (DELEGATION, REGION, PUISSANCE_, FAMILLE_PO, CELLULE)
    delegation: Mapped[str | None] = mapped_column(NVARCHAR(100), nullable=True)
    region: Mapped[str | None] = mapped_column(NVARCHAR(100), nullable=True)
    puissance: Mapped[str | None] = mapped_column(NVARCHAR(50), nullable=True)
    famille_poste: Mapped[str | None] = mapped_column(NVARCHAR(100), nullable=True)
    cellule: Mapped[str | None] = mapped_column(NVARCHAR(100), nullable=True)
    # Source : sir_v1 (tables SIG de SIR v1) ou arcgis (export KMZ validé, migration 5f6a7b8c9d0e)
    source: Mapped[str] = mapped_column(NVARCHAR(20), nullable=False, server_default="sir_v1")
    global_id: Mapped[str | None] = mapped_column(NVARCHAR(40), nullable=True)
    poste_source: Mapped[str | None] = mapped_column(NVARCHAR(255), nullable=True)
    statut_validation: Mapped[str | None] = mapped_column(NVARCHAR(30), nullable=True)
    # 0 : nœud SIR v1 remplacé par le nœud ArcGIS du même poste (plus proposé ni compté)
    est_actif: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1", index=True)
    date_maj: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
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
    # Colonnes complémentaires de Troncon_SIG (IMATFEEDER, SECTIONS, SS, TYPE_CONDU, DELEGATION, DATE_MAJ)
    imat_feeder: Mapped[str | None] = mapped_column(NVARCHAR(100), nullable=True)
    section: Mapped[str | None] = mapped_column(NVARCHAR(100), nullable=True)
    poste_source: Mapped[str | None] = mapped_column(NVARCHAR(255), nullable=True)
    type_conducteur: Mapped[str | None] = mapped_column(NVARCHAR(100), nullable=True)
    delegation: Mapped[str | None] = mapped_column(NVARCHAR(100), nullable=True)
    date_maj: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    # Tronçon du dernier chargement SIG de son départ (recalculé à chaque import) : filtre des écrans
    est_dernier: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    source: Mapped[str] = mapped_column(NVARCHAR(20), nullable=False, server_default="sir_v1")
    global_id: Mapped[str | None] = mapped_column(NVARCHAR(40), nullable=True)
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


class PosteSourceSig(Base):
    """Poste source du SIG (table HFSQL PosteSource_SIG) ; colonnes non reprises gardées dans ``attributs``."""

    __tablename__ = "postes_sources_sig"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    legacy_id: Mapped[str] = mapped_column(NVARCHAR(100), nullable=False, unique=True, index=True)
    nom: Mapped[str | None] = mapped_column(NVARCHAR(255), nullable=True, index=True)
    code: Mapped[str | None] = mapped_column(NVARCHAR(100), nullable=True, index=True)
    delegation: Mapped[str | None] = mapped_column(NVARCHAR(100), nullable=True)
    region: Mapped[str | None] = mapped_column(NVARCHAR(100), nullable=True)
    tension: Mapped[str | None] = mapped_column(NVARCHAR(50), nullable=True)
    coord_x: Mapped[float | None] = mapped_column(Float, nullable=True)
    coord_y: Mapped[float | None] = mapped_column(Float, nullable=True)
    attributs: Mapped[str | None] = mapped_column(NVARCHAR(None), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=MSSQL_NOW
    )


class FeederSig(Base):
    """Départ du SIG (table HFSQL FEEDERS_SIG) ; colonnes non reprises gardées dans ``attributs``."""

    __tablename__ = "feeders_sig"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    legacy_id: Mapped[str] = mapped_column(NVARCHAR(100), nullable=False, unique=True, index=True)
    nom: Mapped[str | None] = mapped_column(NVARCHAR(255), nullable=True, index=True)
    code: Mapped[str | None] = mapped_column(NVARCHAR(100), nullable=True, index=True)
    poste_source: Mapped[str | None] = mapped_column(NVARCHAR(255), nullable=True, index=True)
    delegation: Mapped[str | None] = mapped_column(NVARCHAR(100), nullable=True)
    tension: Mapped[str | None] = mapped_column(NVARCHAR(50), nullable=True)
    feeder_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("feeders.id", ondelete="SET NULL"), nullable=True, index=True
    )
    attributs: Mapped[str | None] = mapped_column(NVARCHAR(None), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=MSSQL_NOW
    )
