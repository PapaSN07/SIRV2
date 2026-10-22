"""Repository — topologie SIG."""

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reseau import Feeder
from app.models.sig import TronconSig as TronconSigOrm
from app.schemas.common import PaginatedResponse
from app.utils.pagination import paginate

_LIBELLE_VOLTAGE_SUFFIXES = (" 30KV", " 6.6KV", " 6.6", " (D4)")
_CODE_VOLTAGE_SUFFIXES = ("_30KV", "_6_6", "_6.6")


def _feeder_sig_nom_aliases(feeder: Feeder) -> set[str]:
    """Noms feeder tels qu'ils apparaissent dans Troncon_SIG (souvent sans suffixe tension)."""
    aliases: set[str] = set()
    if feeder.libelle:
        aliases.add(feeder.libelle.strip())
        for suffix in _LIBELLE_VOLTAGE_SUFFIXES:
            if feeder.libelle.endswith(suffix):
                aliases.add(feeder.libelle[: -len(suffix)].strip())
    if feeder.code:
        aliases.add(feeder.code.strip())
        for suffix in _CODE_VOLTAGE_SUFFIXES:
            if feeder.code.endswith(suffix):
                aliases.add(feeder.code[: -len(suffix)].strip())
    return {a for a in aliases if a}


def _feeder_match_clause(feeder: Feeder):
    """Relie un feeder SIR aux tronçons SIG par id ou par le nom exact du départ."""
    clauses = [TronconSigOrm.feeder_id == feeder.id]
    for alias in _feeder_sig_nom_aliases(feeder):
        clauses.append(TronconSigOrm.nom_feeder == alias)
    return or_(*clauses)


async def get_feeder(db: AsyncSession, feeder_id: int) -> Feeder | None:
    result = await db.execute(select(Feeder).where(Feeder.id == feeder_id))
    return result.scalar_one_or_none()


async def get_troncon_sig(db: AsyncSession, troncon_sig_id: int) -> TronconSigOrm | None:
    result = await db.execute(select(TronconSigOrm).where(TronconSigOrm.id == troncon_sig_id))
    return result.scalar_one_or_none()


async def list_troncons_sig_by_feeder(
    db: AsyncSession,
    feeder: Feeder,
    *,
    page: int = 1,
    page_size: int = 50,
    search: str | None = None,
) -> PaginatedResponse:
    query = (
        select(TronconSigOrm)
        .where(_feeder_match_clause(feeder))
        .order_by(TronconSigOrm.nom_troncon.asc(), TronconSigOrm.id.asc())
    )
    if search:
        pattern = f"%{search.strip()}%"
        query = query.where(
            or_(
                TronconSigOrm.nom_troncon.ilike(pattern),
                TronconSigOrm.nom_noeud_amont.ilike(pattern),
                TronconSigOrm.nom_noeud_aval.ilike(pattern),
                TronconSigOrm.code_noeud_amont.ilike(pattern),
                TronconSigOrm.code_noeud_aval.ilike(pattern),
            )
        )
    return await paginate(
        db,
        query,
        page=page,
        page_size=page_size,
        scalar_type=TronconSigOrm,
        max_page_size=500,
    )


async def find_next_troncon_aval(
    db: AsyncSession,
    feeder: Feeder,
    *,
    code_aval: str | None,
    nom_aval: str | None,
) -> TronconSigOrm | None:
    if not code_aval and not nom_aval:
        return None
    conditions = [_feeder_match_clause(feeder)]
    match_parts = []
    if code_aval:
        match_parts.append(TronconSigOrm.code_noeud_amont == code_aval)
    if nom_aval:
        match_parts.append(func.upper(TronconSigOrm.nom_noeud_amont) == func.upper(nom_aval))
    if len(match_parts) == 1:
        conditions.append(match_parts[0])
    else:
        conditions.append(or_(*match_parts))
    result = await db.execute(select(TronconSigOrm).where(*conditions).limit(1))
    return result.scalar_one_or_none()


async def build_chaine_aval(
    db: AsyncSession,
    feeder: Feeder,
    start: TronconSigOrm,
    *,
    limit: int = 3,
) -> list[TronconSigOrm]:
    """Chaîne aval depuis le tronçon sélectionné (segments successifs)."""
    chain: list[TronconSigOrm] = []
    current: TronconSigOrm | None = start
    seen: set[int] = set()

    while current is not None and len(chain) < limit:
        if current.id in seen:
            break
        seen.add(current.id)
        chain.append(current)
        current = await find_next_troncon_aval(
            db,
            feeder,
            code_aval=current.code_noeud_aval,
            nom_aval=current.nom_noeud_aval,
        )
    return chain
