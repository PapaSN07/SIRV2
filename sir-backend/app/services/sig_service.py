"""Service métier — topologie SIG."""

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.utilisateurs import Utilisateur
from app.repositories import sig_repository as repo
from app.schemas.common import PaginatedResponse
from app.schemas.sig import TronconSigChaineResponse, TronconSigResponse
from app.services.interruption_distribution_service import READ_ROLES, _ensure_can_read, _user_role_names
from app.core.rbac_helpers import is_superadmin

_MAX_CHAIN = 10


def _ensure_sig_read(user: Utilisateur) -> None:
    _ensure_can_read(user)
    if is_superadmin(user):
        return
    if not _user_role_names(user).intersection(READ_ROLES):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "status": "error",
                "data": None,
                "error": "Accès topologie SIG non autorisé",
            },
        )


def _to_troncon_response(item) -> TronconSigResponse:
    return TronconSigResponse.model_validate(item)


async def list_troncons_sig(
    db: AsyncSession,
    current_user: Utilisateur,
    *,
    feeder_id: int,
    page: int = 1,
    page_size: int = 50,
    search: str | None = None,
) -> PaginatedResponse[TronconSigResponse]:
    _ensure_sig_read(current_user)
    feeder = await repo.get_feeder(db, feeder_id)
    if feeder is None or not feeder.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "status": "error",
                "data": None,
                "error": f"Feeder {feeder_id} introuvable ou inactif",
            },
        )

    result = await repo.list_troncons_sig_by_feeder(
        db, feeder, page=page, page_size=page_size, search=search
    )
    return PaginatedResponse(
        items=[_to_troncon_response(i) for i in result.items],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
    )


async def get_chaine_aval(
    db: AsyncSession,
    current_user: Utilisateur,
    troncon_sig_id: int,
    *,
    limit: int = 3,
) -> TronconSigChaineResponse:
    _ensure_sig_read(current_user)
    if limit < 1 or limit > _MAX_CHAIN:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "status": "error",
                "data": None,
                "error": f"limit doit être entre 1 et {_MAX_CHAIN}",
            },
        )

    troncon = await repo.get_troncon_sig(db, troncon_sig_id)
    if troncon is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "status": "error",
                "data": None,
                "error": f"Tronçon SIG {troncon_sig_id} introuvable",
            },
        )

    feeder = None
    if troncon.feeder_id is not None:
        feeder = await repo.get_feeder(db, troncon.feeder_id)
    if feeder is None and troncon.nom_feeder:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "status": "error",
                "data": None,
                "error": "Tronçon SIG sans feeder résolu — import SIG incomplet",
            },
        )
    if feeder is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "status": "error",
                "data": None,
                "error": "Feeder introuvable pour ce tronçon SIG",
            },
        )

    chain = await repo.build_chaine_aval(db, feeder, troncon, limit=limit)
    return TronconSigChaineResponse(
        troncon=_to_troncon_response(chain[0]),
        chaine_aval=[_to_troncon_response(t) for t in chain[1:]],
    )
