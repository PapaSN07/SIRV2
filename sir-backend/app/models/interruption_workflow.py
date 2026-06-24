"""Étapes opérationnelles workflow interruption distribution (7 onglets legacy)."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, NVARCHAR, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.defaults import MSSQL_NOW


class InterruptionWorkflowStep(Base):
    """Données workflow opérationnel — 1 ligne par interruption distribution.

    Onglets legacy : déclenchement, interpellation PDM, tronçonnement, localisation,
    réparation, remise. L'onglet « clients » s'appuie sur poste_interruptions.
    """

    __tablename__ = "interruption_workflow_steps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    interruption_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("interruptions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Déclenchement
    date_debut_declenchement: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    date_fin_declenchement: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    duree_declenchement_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Interpellation PDM
    date_interpellation_pdm: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    date_arrivee_pdm: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    duree_interpellation_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Tronçonnement
    date_debut_tronconnement: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    date_fin_tronconnement: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    duree_tronconnement_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    troncon_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("troncons.id", ondelete="NO ACTION"), nullable=True, index=True
    )
    troncon_sig_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("troncons_sig.id", ondelete="NO ACTION"), nullable=True, index=True
    )

    # Localisation
    date_debut_localisation: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    date_fin_localisation: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    duree_localisation_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Réparation
    date_debut_reparation: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    date_fin_reparation: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    duree_reparation_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Remise
    date_debut_remise: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    date_fin_remise: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    duree_remise_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # SIG (libellés temporaires — FK noeuds en phase C)
    noeud_amont_libelle: Mapped[str | None] = mapped_column(NVARCHAR(255), nullable=True)
    noeud_aval_libelle: Mapped[str | None] = mapped_column(NVARCHAR(255), nullable=True)

    responsable_matricule: Mapped[int | None] = mapped_column(Integer, nullable=True)
    observations_workflow: Mapped[str | None] = mapped_column(NVARCHAR(2000), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=MSSQL_NOW
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        server_default=MSSQL_NOW,
        onupdate=func.now(),
    )

    interruption: Mapped["Interruption"] = relationship(  # noqa: F821
        "Interruption", back_populates="workflow_step", lazy="select"
    )
    troncon: Mapped["Troncon | None"] = relationship("Troncon", lazy="select")  # noqa: F821
    troncon_sig: Mapped["TronconSig | None"] = relationship(  # noqa: F821
        "TronconSig", back_populates="workflow_steps", lazy="select"
    )
