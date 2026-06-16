from datetime import datetime

from sqlalchemy import NVARCHAR, Boolean, CheckConstraint, DateTime, ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.defaults import MSSQL_NOW

CANAL_VALUES = ("sms", "email")
STATUT_ENVOI_VALUES = ("en_attente", "envoye", "echec")


class Destinataire(Base):
    """Destinataire de notifications (SMS/Email) lié à un utilisateur ou saisi manuellement."""

    __tablename__ = "destinataires"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    utilisateur_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("utilisateurs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    nom: Mapped[str] = mapped_column(NVARCHAR(200), nullable=False)
    telephone: Mapped[str | None] = mapped_column(NVARCHAR(20), nullable=True)
    email: Mapped[str | None] = mapped_column(NVARCHAR(255), nullable=True)
    service_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("services.id", ondelete="SET NULL"), nullable=True, index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Relationships
    utilisateur: Mapped["Utilisateur | None"] = relationship("Utilisateur", foreign_keys=[utilisateur_id], lazy="select")  # noqa: F821
    service: Mapped["Service | None"] = relationship("Service", foreign_keys=[service_id], lazy="select")  # noqa: F821
    sms_envoyes: Mapped[list["SmsEnvoye"]] = relationship(
        "SmsEnvoye", back_populates="destinataire", lazy="select"
    )
    emails_envoyes: Mapped[list["EmailEnvoye"]] = relationship(
        "EmailEnvoye", back_populates="destinataire", lazy="select"
    )


class SmsEnvoye(Base):
    """Trace d'un SMS envoyé (interruption, NAPT, alerte…)."""

    __tablename__ = "sms_envoyes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    destinataire_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("destinataires.id", ondelete="NO ACTION"), nullable=False, index=True
    )
    # Reference to the triggering entity (interruption, napt…)
    entity_type: Mapped[str | None] = mapped_column(NVARCHAR(50), nullable=True)
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    contenu: Mapped[str] = mapped_column(NVARCHAR(1000), nullable=False)
    statut: Mapped[str] = mapped_column(
        NVARCHAR(20), nullable=False, default="en_attente", index=True
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    erreur: Mapped[str | None] = mapped_column(NVARCHAR(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=MSSQL_NOW
    )

    __table_args__ = (
        CheckConstraint(
            "statut IN ('en_attente', 'envoye', 'echec')",
            name="ck_sms_statut",
        ),
    )

    # Relationships
    destinataire: Mapped["Destinataire"] = relationship(
        "Destinataire", back_populates="sms_envoyes"
    )


class EmailEnvoye(Base):
    """Trace d'un Email envoyé (interruption, NAPT, rapport…)."""

    __tablename__ = "emails_envoyes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    destinataire_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("destinataires.id", ondelete="NO ACTION"), nullable=False, index=True
    )
    entity_type: Mapped[str | None] = mapped_column(NVARCHAR(50), nullable=True)
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sujet: Mapped[str] = mapped_column(NVARCHAR(500), nullable=False)
    corps: Mapped[str] = mapped_column(NVARCHAR(4000), nullable=False)
    statut: Mapped[str] = mapped_column(
        NVARCHAR(20), nullable=False, default="en_attente", index=True
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    erreur: Mapped[str | None] = mapped_column(NVARCHAR(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=MSSQL_NOW
    )

    __table_args__ = (
        CheckConstraint(
            "statut IN ('en_attente', 'envoye', 'echec')",
            name="ck_email_statut",
        ),
    )

    # Relationships
    destinataire: Mapped["Destinataire"] = relationship(
        "Destinataire", back_populates="emails_envoyes"
    )
