"""Base clients SAIFI/SAIDI : synchronisation BI_ODS (quotidienne) et import du fichier H2MC déposé."""

from __future__ import annotations

import asyncio
import dataclasses
import logging
from pathlib import Path

from app.workers.celery_app import celery_app
from app.workers.db import WorkerSessionLocal

logger = logging.getLogger(__name__)


async def _synchroniser() -> dict[str, object]:
    from app.services import base_clients_service as svc

    async with WorkerSessionLocal() as db:
        return dataclasses.asdict(await svc.synchroniser_bi_ods(db))


async def _importer_fichier(chemin: str, annee: int, mois: int) -> dict[str, object]:
    from app.services import base_clients_service as svc

    brutes = svc.lire_fichier(Path(chemin))
    async with WorkerSessionLocal() as db:
        return dataclasses.asdict(await svc.importer(db, annee, mois, brutes, svc.SOURCE_FICHIER))


@celery_app.task(name="synchroniser_contrats_ur")
def synchroniser_contrats_ur_task() -> dict[str, object]:
    from app.core.config import settings

    if not settings.bi_ods_odbc:
        logger.info("Base clients : BI_ODS non configurée, synchronisation ignorée")
        return {"ignore": "BI_ODS_ODBC vide"}
    return asyncio.run(_synchroniser())


@celery_app.task(name="importer_contrats_fichier")
def importer_contrats_fichier_task(chemin: str, annee: int, mois: int) -> dict[str, object]:
    try:
        return asyncio.run(_importer_fichier(chemin, annee, mois))
    finally:
        Path(chemin).unlink(missing_ok=True)


async def _recalculer_postes(postes: list[int]) -> dict[str, object]:
    from app.services import atelier_clients_service as atelier

    async with WorkerSessionLocal() as db:
        return await atelier.recalculer_postes(db, postes)


@celery_app.task(name="recalculer_clients_postes")
def recalculer_clients_postes_task(postes: list[int]) -> dict[str, object]:
    """Après validation d'un lien poste ↔ UR dans l'atelier clients."""
    return asyncio.run(_recalculer_postes(postes))
