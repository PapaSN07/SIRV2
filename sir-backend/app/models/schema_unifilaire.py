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

    poste: Mapped["Poste | None"] = relationship("Poste", lazy="select")  # noqa: F821


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
