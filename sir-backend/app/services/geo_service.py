"""Service métier — organisation géographique (lecture seule, phase 2.2)."""

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import geo_repository
from app.schemas.geo import (
    AgenceResponse,
    DelegationResponse,
    RegionResponse,
    ServiceResponse,
)


def _region_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={
            "status": "error",
            "data": None,
            "error": "Région introuvable",
        },
    )


def _delegation_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={
            "status": "error",
            "data": None,
            "error": "Délégation introuvable",
        },
    )


def _agence_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={
            "status": "error",
            "data": None,
            "error": "Agence introuvable",
        },
    )


async def list_regions(db: AsyncSession) -> list[RegionResponse]:
    records = await geo_repository.list_regions(db)
    return [RegionResponse.model_validate(r) for r in records]


async def list_delegations(
    db: AsyncSession,
    region_id: int,
) -> list[DelegationResponse]:
    region = await geo_repository.get_region_by_id(db, region_id)
    if region is None:
        raise _region_not_found()

    records = await geo_repository.list_delegations_by_region(db, region_id)
    return [DelegationResponse.model_validate(r) for r in records]


async def list_agences(
    db: AsyncSession,
    delegation_id: int,
) -> list[AgenceResponse]:
    delegation = await geo_repository.get_delegation_by_id(db, delegation_id)
    if delegation is None:
        raise _delegation_not_found()

    records = await geo_repository.list_agences_by_delegation(db, delegation_id)
    return [AgenceResponse.model_validate(r) for r in records]


async def list_services(
    db: AsyncSession,
    agence_id: int,
) -> list[ServiceResponse]:
    agence = await geo_repository.get_agence_by_id(db, agence_id)
    if agence is None:
        raise _agence_not_found()

    records = await geo_repository.list_services_by_agence(db, agence_id)
    return [ServiceResponse.model_validate(r) for r in records]


async def list_services_by_region(
    db: AsyncSession,
    region_id: int,
) -> list[ServiceResponse]:
    region = await geo_repository.get_region_by_id(db, region_id)
    if region is None:
        raise _region_not_found()

    records = await geo_repository.list_services_by_region(db, region_id)
    return [ServiceResponse.model_validate(r) for r in records]
