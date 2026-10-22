"""Workflow opérationnel interruption distribution — étapes chaînées."""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, NVARCHAR, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.defaults import MSSQL_NOW

ETAPE_DECLENCHEMENT = "declenchement"
ETAPE_INTERPELLATION = "interpellation_pdm"
ETAPE_TRONCONNEMENT = "tronconnement"
ETAPE_LOCALISATION = "localisation"
ETAPE_REPARATION = "reparation"
ETAPE_REMISE = "remise"


class EtapeWorkflow(Base):
    """Référentiel des étapes ; `etape_suivante_id` définit l'enchaînement."""

    __tablename__ = "etapes_workflow"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    code: Mapped[str] = mapped_column(NVARCHAR(30), nullable=False, unique=True)
    libelle_etape_workflow: Mapped[str] = mapped_column(NVARCHAR(100), nullable=False)
    ordre: Mapped[int] = mapped_column(Integer, nullable=False)
    etape_suivante_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("etapes_workflow.id", ondelete="NO ACTION"), nullable=True
    )


class Workflow(Base):
    """Une ligne par (interruption, étape). L'étape suivante n'est saisissable
    qu'une fois `date_fin` renseignée sur l'étape précédente."""

    __tablename__ = "workflows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    interruption_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("interruptions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    etape_workflow_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("etapes_workflow.id", ondelete="NO ACTION"), nullable=False, index=True
    )
    date_debut: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    date_fin: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    observation: Mapped[str | None] = mapped_column(NVARCHAR(2000), nullable=True)

    # Données propres à l'étape tronçonnement
    troncon_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("troncons.id", ondelete="NO ACTION"), nullable=True, index=True
    )
    troncon_sig_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("troncons_sig.id", ondelete="NO ACTION"), nullable=True, index=True
    )
    noeud_amont_libelle: Mapped[str | None] = mapped_column(NVARCHAR(255), nullable=True)
    noeud_aval_libelle: Mapped[str | None] = mapped_column(NVARCHAR(255), nullable=True)
    responsable_matricule: Mapped[int | None] = mapped_column(Integer, nullable=True)

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
        UniqueConstraint("interruption_id", "etape_workflow_id", name="uq_workflow_interruption_etape"),
        CheckConstraint(
            "date_fin IS NULL OR date_debut IS NULL OR date_fin >= date_debut",
            name="ck_workflow_dates",
        ),
    )

    interruption: Mapped["Interruption"] = relationship(  # noqa: F821
        "Interruption", back_populates="workflows", lazy="select"
    )
    etape: Mapped["EtapeWorkflow"] = relationship("EtapeWorkflow", lazy="select")
    troncon: Mapped["Troncon | None"] = relationship("Troncon", lazy="select")  # noqa: F821
    troncon_sig: Mapped["TronconSig | None"] = relationship(  # noqa: F821
        "TronconSig", back_populates="workflows", lazy="select"
    )
