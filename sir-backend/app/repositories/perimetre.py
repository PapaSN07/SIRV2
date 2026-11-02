"""Périmètre géographique des calculs (indicateurs, pilotage, rapports).

SIR v1 range chaque interruption dans une région d'exploitation, Dakar (BCC) ou Régions (BRC),
et les services travaillent dans les deux : une liste de services ne suffit pas à décrire une
région. Un périmètre régional = tous les services + la région, portée :
  - côté interruptions par ``interruptions.region_id`` ;
  - côté base clients par la région des services qui portent ``nombre_client_mois``
    (services représentatifs SIR v1 : DD → Dakar, BRC → Régions).

La région est posée par ``indicateurs_service._load_service_ids`` (à chaque résolution de
périmètre, y compris national pour l'effacer) et lue par les filtres ci-dessous, ce qui évite de
la passer à chacune des fonctions de calcul qui prennent déjà ``service_ids``.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

from sqlalchemy import ColumnElement, and_, select

from app.models.geo import Service
from app.models.indicateurs import NombreClientMois
from app.models.interruptions import Interruption

_region: ContextVar[int | None] = ContextVar("perimetre_region", default=None)


def definir_region(region_id: int | None) -> None:
    """Région du calcul en cours (None : national ou service)."""
    _region.set(region_id)


def region_courante() -> int | None:
    return _region.get()


@contextmanager
def perimetre_region(region_id: int | None) -> Iterator[None]:
    """Bloc de calcul sur une région, rétablit le périmètre précédent en sortie."""
    jeton = _region.set(region_id)
    try:
        yield
    finally:
        _region.reset(jeton)


def interruptions_du_perimetre(service_ids: list[int]) -> ColumnElement[bool]:
    """Filtre des interruptions : services du périmètre et, en régional, région de l'interruption."""
    condition = Interruption.service_id.in_(service_ids)
    region_id = _region.get()
    if region_id is None:
        return condition
    return and_(condition, Interruption.region_id == region_id)


def clients_du_perimetre(service_ids: list[int]) -> ColumnElement[bool]:
    """Filtre de la base clients : services du périmètre et, en régional, services de la région."""
    condition = NombreClientMois.service_id.in_(service_ids)
    region_id = _region.get()
    if region_id is None:
        return condition
    return and_(condition, NombreClientMois.service_id.in_(select(Service.id).where(Service.region_id == region_id)))
