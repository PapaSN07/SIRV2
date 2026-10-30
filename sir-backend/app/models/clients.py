"""Base clients SAIFI/SAIDI (reprise de l'atelier SAIFI/SAIDI de l'application bureau SIR).

- ContratsUniteReleve : photo mensuelle des contrats par unité de relève (UR, ex. 1100200I) ;
- PosteUniteReleve : UR rattachées à un poste. Clients d'un poste = somme des contrats de ses UR.
"""

from datetime import datetime

from sqlalchemy import NVARCHAR, CheckConstraint, DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

STATUTS_LIEN_UR = ("valide", "ajout_propose", "suppression_proposee")


class ContratsUniteReleve(Base):
    __tablename__ = "contrats_unites_releve"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    annee: Mapped[int] = mapped_column(Integer, nullable=False)
    mois: Mapped[int] = mapped_column(Integer, nullable=False)
    unite_releve: Mapped[str] = mapped_column(NVARCHAR(20), nullable=False)
    libelle: Mapped[str | None] = mapped_column(NVARCHAR(150), nullable=True)
    code_agence: Mapped[str | None] = mapped_column(NVARCHAR(10), nullable=True)
    delegation: Mapped[str | None] = mapped_column(NVARCHAR(10), nullable=True)
    agence_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("agences.id"), nullable=True)
    nb_contrats: Mapped[int] = mapped_column(Integer, nullable=False)
    date_maj: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    # « bi_ods » (SSIS) ou « fichier » (Excel déposé)
    source: Mapped[str] = mapped_column(NVARCHAR(20), nullable=False)

    __table_args__ = (
        UniqueConstraint("annee", "mois", "unite_releve", name="uq_contrats_ur_mois"),
        CheckConstraint("mois BETWEEN 1 AND 12", name="ck_contrats_ur_mois"),
    )


class PosteUniteReleve(Base):
    __tablename__ = "postes_unites_releve"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    poste_id: Mapped[int] = mapped_column(Integer, ForeignKey("postes.id", ondelete="CASCADE"), nullable=False, index=True)
    unite_releve: Mapped[str] = mapped_column(NVARCHAR(20), nullable=False, index=True)
    statut: Mapped[str] = mapped_column(NVARCHAR(25), nullable=False, default="valide")
    modifie_par_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("utilisateurs.id"), nullable=True)
    modifie_le: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    valide_par_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("utilisateurs.id"), nullable=True)
    valide_le: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)

    __table_args__ = (
        UniqueConstraint("poste_id", "unite_releve", name="uq_poste_ur"),
        CheckConstraint("statut IN ('valide', 'ajout_propose', 'suppression_proposee')", name="ck_poste_ur_statut"),
    )
