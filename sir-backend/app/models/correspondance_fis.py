"""Correspondances FIS administrées : libellé du fichier FIS → entrée du Référentiel.

Une correspondance rattache un libellé FIS normalisé (minuscules, espaces de bord retirés,
espace insécable remplacé) à une nature, une cause, un siège ou une signalisation. Créée et
supprimée par l'Admin SCR, lue par l'import FIS avant la table interne et la recherche par libellé.
"""

from datetime import datetime

from sqlalchemy import NVARCHAR, Boolean, CheckConstraint, DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.defaults import MSSQL_NOW

CATEGORIES_FIS = ("nature", "cause", "siege", "signalisation")


class CorrespondanceFis(Base):
    __tablename__ = "correspondances_fis"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    categorie: Mapped[str] = mapped_column(NVARCHAR(20), nullable=False)
    libelle_fis: Mapped[str] = mapped_column(NVARCHAR(200), nullable=False)
    nature_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("natures.id", ondelete="NO ACTION"), nullable=True
    )
    cause_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("causes.id", ondelete="NO ACTION"), nullable=True)
    siege_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("sieges.id", ondelete="NO ACTION"), nullable=True)
    signalisation_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("signalisations.id", ondelete="NO ACTION"), nullable=True
    )
    # Cause seulement : None = règle de la table interne de l'import
    is_force_majeure: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    created_by_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("utilisateurs.id", ondelete="NO ACTION"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=MSSQL_NOW
    )  # DATETIME2 en base (migration)

    # Chargées avec la correspondance (l'import les lit hors de tout chargement paresseux)
    nature: Mapped["Nature | None"] = relationship("Nature", lazy="joined")  # noqa: F821
    cause: Mapped["Cause | None"] = relationship("Cause", lazy="joined")  # noqa: F821
    siege: Mapped["Siege | None"] = relationship("Siege", lazy="joined")  # noqa: F821
    signalisation: Mapped["Signalisation | None"] = relationship("Signalisation", lazy="joined")  # noqa: F821

    __table_args__ = (
        UniqueConstraint("categorie", "libelle_fis", name="uq_correspondances_fis_categorie_libelle"),
        CheckConstraint(
            "categorie IN ('nature', 'cause', 'siege', 'signalisation')",
            name="ck_correspondances_fis_categorie",
        ),
        CheckConstraint(
            "(categorie = 'nature' AND nature_id IS NOT NULL AND cause_id IS NULL AND siege_id IS NULL "
            "AND signalisation_id IS NULL) "
            "OR (categorie = 'cause' AND cause_id IS NOT NULL AND nature_id IS NULL AND siege_id IS NULL "
            "AND signalisation_id IS NULL) "
            "OR (categorie = 'siege' AND siege_id IS NOT NULL AND nature_id IS NULL AND cause_id IS NULL "
            "AND signalisation_id IS NULL) "
            "OR (categorie = 'signalisation' AND signalisation_id IS NOT NULL AND nature_id IS NULL "
            "AND cause_id IS NULL AND siege_id IS NULL)",
            name="ck_correspondances_fis_cible",
        ),
        CheckConstraint(
            "is_force_majeure IS NULL OR categorie = 'cause'",
            name="ck_correspondances_fis_force_majeure",
        ),
    )
