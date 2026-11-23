"""Schémas unifilaires (PDF AutoCAD) : postes cliquables, graphe des lignes et tuiles d'affichage.

Remplis par ``scripts/migration/import_schema_unifilaire.py`` (lecture du PDF) ; l'API ne fait que lire,
sauf l'association manuelle d'un poste du schéma à un poste SIRV2.
"""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    NVARCHAR,
    PrimaryKeyConstraint,
    SmallInteger,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.defaults import MSSQL_NOW


class SchemaUnifilaire(Base):
    __tablename__ = "schemas_unifilaires"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nom: Mapped[str] = mapped_column(NVARCHAR(150), nullable=False)
    fichier: Mapped[str] = mapped_column(NVARCHAR(255), nullable=False)
    region_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("regions.id", ondelete="NO ACTION"), nullable=True, index=True
    )
    largeur: Mapped[float] = mapped_column(Float, nullable=False)
    hauteur: Mapped[float] = mapped_column(Float, nullable=False)
    zoom_max: Mapped[int] = mapped_column(Integer, nullable=False)
    # Graphe des lignes (JSON gzip : coords, aretes, postes) — voir schema_unifilaire_graphe
    graphe: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    nb_postes: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="1")
    importe_le: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, server_default=MSSQL_NOW)

    region: Mapped["Region | None"] = relationship("Region", lazy="select")  # noqa: F821


class SchemaUnifilairePoste(Base):
    __tablename__ = "schema_unifilaire_postes"
    __table_args__ = (UniqueConstraint("schema_id", "rang", name="uq_schema_unifilaire_postes_rang"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    schema_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("schemas_unifilaires.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Ordre du poste dans le graphe (graphe["postes"][rang] = nœud)
    rang: Mapped[int] = mapped_column(Integer, nullable=False)
    libelle: Mapped[str | None] = mapped_column(NVARCHAR(200), nullable=True)
    forme: Mapped[str] = mapped_column(NVARCHAR(10), nullable=False)
    puissance_kva: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Boîtier du symbole et du libellé (points PDF, origine en haut à gauche)
    x0: Mapped[float] = mapped_column(Float, nullable=False)
    y0: Mapped[float] = mapped_column(Float, nullable=False)
    x1: Mapped[float] = mapped_column(Float, nullable=False)
    y1: Mapped[float] = mapped_column(Float, nullable=False)
    lx0: Mapped[float | None] = mapped_column(Float, nullable=True)
    ly0: Mapped[float | None] = mapped_column(Float, nullable=True)
    lx1: Mapped[float | None] = mapped_column(Float, nullable=True)
    ly1: Mapped[float | None] = mapped_column(Float, nullable=True)
    poste_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("postes.id", ondelete="NO ACTION"), nullable=True, index=True
    )
    # auto (même nom), manuel (choisi par un administrateur), ambigu (plusieurs postes du même nom)
    rapprochement: Mapped[str | None] = mapped_column(NVARCHAR(10), nullable=True)
    # Nœud SIG rapproché : auto (même nom), manuel, ambigu (plusieurs nœuds SIG du même nom)
    noeud_sig_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("noeuds_sig.id", name="fk_schema_unifilaire_postes_noeud_sig"), nullable=True, index=True
    )
    rapprochement_sig: Mapped[str | None] = mapped_column(NVARCHAR(10), nullable=True)
    # Décision SIR quand le poste n'est pas relié : inactif (hors service, non repris) ou a_creer
    statut_sir: Mapped[str | None] = mapped_column(NVARCHAR(10), nullable=True)

    poste: Mapped["Poste | None"] = relationship("Poste", lazy="select")  # noqa: F821
    noeud_sig: Mapped["NoeudSig | None"] = relationship("NoeudSig", lazy="select")  # noqa: F821


class SchemaUnifilaireTuile(Base):
    __tablename__ = "schema_unifilaire_tuiles"
    __table_args__ = (PrimaryKeyConstraint("schema_id", "z", "x", "y", name="pk_schema_unifilaire_tuiles"),)

    schema_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("schemas_unifilaires.id", ondelete="CASCADE"), nullable=False
    )
    z: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    x: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    y: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    contenu: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)


STATUTS_DEMANDE = ("propose", "valide", "rejete")


class PosteACreer(Base):
    """Proposition de création d'un poste dans SIR, depuis le rapprochement Schéma / SIG / SIR."""

    __tablename__ = "postes_a_creer"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    schema_poste_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("schema_unifilaire_postes.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # Repères gardés si le schéma est réimporté (le poste du schéma est alors recréé)
    schema_nom: Mapped[str | None] = mapped_column(NVARCHAR(150), nullable=True)
    libelle_schema: Mapped[str | None] = mapped_column(NVARCHAR(200), nullable=True)
    libelle: Mapped[str] = mapped_column(NVARCHAR(200), nullable=False)
    poste_source_id: Mapped[int] = mapped_column(Integer, ForeignKey("postes_sources.id"), nullable=False)
    feeder_id: Mapped[int] = mapped_column(Integer, ForeignKey("feeders.id"), nullable=False, index=True)
    noeud_sig_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("noeuds_sig.id"), nullable=True)
    statut: Mapped[str] = mapped_column(NVARCHAR(10), nullable=False, server_default="propose", index=True)
    motif_rejet: Mapped[str | None] = mapped_column(NVARCHAR(500), nullable=True)
    poste_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("postes.id"), nullable=True)
    propose_par_id: Mapped[int] = mapped_column(Integer, ForeignKey("utilisateurs.id"), nullable=False)
    propose_le: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, server_default=MSSQL_NOW)
    traite_par_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("utilisateurs.id"), nullable=True)
    traite_le: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)

    poste_source: Mapped["PosteSource"] = relationship("PosteSource", lazy="select")  # noqa: F821
    feeder: Mapped["Feeder"] = relationship("Feeder", lazy="select")  # noqa: F821
    noeud_sig: Mapped["NoeudSig | None"] = relationship("NoeudSig", lazy="select")  # noqa: F821
    propose_par: Mapped["Utilisateur"] = relationship(  # noqa: F821
        "Utilisateur", foreign_keys=[propose_par_id], lazy="select"
    )
    traite_par: Mapped["Utilisateur | None"] = relationship(  # noqa: F821
        "Utilisateur", foreign_keys=[traite_par_id], lazy="select"
    )
