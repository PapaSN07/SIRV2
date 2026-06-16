"""Service — envoi email SMTP async (Sprint 8.2)."""

import asyncio
import logging
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.repositories import email_repository as repo

logger = logging.getLogger(__name__)


def _send_smtp_sync(*, to_email: str, sujet: str, corps: str) -> None:
    if not settings.smtp_host:
        raise RuntimeError("SMTP non configuré")

    message = MIMEMultipart("alternative")
    message["Subject"] = sujet
    message["From"] = settings.smtp_user or "sir@senelec.sn"
    message["To"] = to_email
    message.attach(MIMEText(corps, "html", "utf-8"))

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as smtp:
        if settings.smtp_user:
            smtp.starttls()
            smtp.login(settings.smtp_user, settings.smtp_password)
        smtp.sendmail(message["From"], [to_email], message.as_string())


async def send_direct(*, to_email: str, sujet: str, corps: str) -> dict[str, str]:
    try:
        if settings.smtp_host:
            await asyncio.to_thread(
                _send_smtp_sync,
                to_email=to_email,
                sujet=sujet,
                corps=corps,
            )
        else:
            logger.warning("SMTP mock direct to=%s sujet=%s", to_email, sujet)
        return {"statut": "envoye"}
    except Exception as exc:
        logger.exception("send_direct failed to=%s", to_email)
        raise RuntimeError(str(exc)) from exc


async def send_email_record(db: AsyncSession, email_id: int) -> dict[str, str]:
    record = await repo.get_by_id(db, email_id)
    if record is None:
        raise ValueError(f"Email introuvable: id={email_id}")

    destinataire = record.destinataire
    if destinataire is None or not destinataire.email:
        await repo.update_statut(
            db,
            record,
            statut="echec",
            erreur="Destinataire sans email",
        )
        return {"statut": "echec"}

    try:
        if settings.smtp_host:
            await asyncio.to_thread(
                _send_smtp_sync,
                to_email=destinataire.email,
                sujet=record.sujet,
                corps=record.corps,
            )
        else:
            logger.warning(
                "SMTP mock — email simulé id=%s to=%s sujet=%s",
                email_id,
                destinataire.email,
                record.sujet,
            )

        await repo.update_statut(
            db,
            record,
            statut="envoye",
            sent_at=datetime.now(),
        )
        return {"statut": "envoye"}
    except Exception as exc:
        await repo.update_statut(
            db,
            record,
            statut="echec",
            erreur=str(exc)[:500],
        )
        raise
