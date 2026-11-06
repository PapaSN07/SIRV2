"""Service — aperçus graphiques des rapports (page Rapports).

Les chiffres du rapport hebdomadaire d'exploitation DD et du rapport mensuel distribution,
pour les graphiques affichés avant de télécharger le fichier. Calculs légers (une ou deux
semaines, un mois d'indicateurs déjà en cache) ; résultat gardé une heure dans Redis.
"""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import HTTPException, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac_helpers import is_superadmin
from app.models.utilisateurs import Utilisateur
from app.repositories import rapport_hebdo_repository as hebdo_repo
from app.schemas.rapports import (
    ApercuHebdoDDResponse,
    ApercuMensuelDistributionResponse,
    ApercuSerie,
    ApercuValeur,
)
from app.services import rapport_hebdo_dd_service as hebdo
from app.services import rapport_mensuel_service
from app.services.indicateurs_cache_service import get_cached, set_cached
from app.services.rapport_generation_service import (
    _HEBDO_DD_ROLES,
    _assert_distribution_rapport_role,
    _resolve_region_id,
    _user_role_names,
)


def construire_apercu_hebdo(semaine: hebdo.StatsSemaine, precedente: hebdo.StatsSemaine) -> ApercuHebdoDDResponse:
    """Indicateurs, catégories HTA / HTB, END par service et par jour (semaine et précédente)."""
    categories = [
        ApercuSerie(
            libelle=libelle,
            nombre=semaine.par_categorie.get(cle, hebdo.Compte()).nombre,
            end_mwh=round(semaine.par_categorie.get(cle, hebdo.Compte()).end_mwh, 3),
            nombre_precedent=precedente.par_categorie.get(cle, hebdo.Compte()).nombre,
            end_mwh_precedent=round(precedente.par_categorie.get(cle, hebdo.Compte()).end_mwh, 3),
        )
        for cle, libelle in hebdo.CATEGORIES_HTA + hebdo.CATEGORIES_HTB
    ]
    total_end = sum(semaine.end_service.values()) or 0.0
    services = [
        ApercuSerie(
            libelle=code,
            end_mwh=round(end, 3),
            end_mwh_precedent=round(precedente.end_service.get(code, 0.0), 3),
            part_pct=round(100 * end / total_end, 1) if total_end else None,
        )
        for code, end in sorted(semaine.end_service.items(), key=lambda kv: -kv[1])
    ]
    jours = []
    for i, nom in enumerate(hebdo.JOURS):
        jour = semaine.debut + timedelta(days=i)
        lignes = [c for (j, cat, _), c in semaine.par_jour.items() if j == i and cat not in (hebdo.HTB_DELESTAGE, hebdo.HTB_AUTRES)]
        jours.append(
            ApercuSerie(
                libelle=f"{nom} {jour:%d/%m}",
                nombre=sum(c.nombre for c in lignes),
                end_mwh=round(sum(c.end_mwh for c in lignes), 3),
            )
        )
    hta, hta_prec = semaine.total_hta, precedente.total_hta
    return ApercuHebdoDDResponse(
        debut=semaine.debut,
        fin=semaine.fin,
        numero=semaine.numero,
        numero_precedent=precedente.numero,
        indicateurs=[
            ApercuValeur(libelle="Interruptions HTA", valeur=hta.nombre, precedent=hta_prec.nombre),
            ApercuValeur(libelle="END HTA (MWh)", valeur=round(hta.end_mwh, 3), precedent=round(hta_prec.end_mwh, 3)),
            ApercuValeur(libelle="SAIFI", valeur=round(semaine.saifi, 4), precedent=round(precedente.saifi, 4)),
            ApercuValeur(libelle="SAIDI (h)", valeur=round(semaine.saidi_h, 4), precedent=round(precedente.saidi_h, 4)),
        ],
        categories=categories,
        services=services,
        jours=jours,
    )


async def apercu_hebdo_dd(
    db: AsyncSession, redis: Redis, user: Utilisateur, *, date_fin: date | None = None
) -> ApercuHebdoDDResponse:
    if not (is_superadmin(user) or _user_role_names(user) & _HEBDO_DD_ROLES):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"status": "error", "data": None, "error": "Rapport hebdomadaire DD réservé à l'Admin SCR et à l'Admin SAQS"},
        )
    reference = date_fin + timedelta(days=1) if date_fin else date.today()
    debut, fin = hebdo.semaine_samedi_vendredi(reference)
    cle = f"rapports:apercu:hebdo-dd:{fin.isoformat()}"
    cached = await get_cached(redis, cle)
    if isinstance(cached, dict) and "jours" in cached:
        return ApercuHebdoDDResponse.model_validate(cached)
    service_ids = [sid for sid, _, _ in await hebdo_repo.services_distribution(db)]
    semaine, _ = await hebdo._semaine(db, debut, fin, service_ids)
    precedente, _ = await hebdo._semaine(db, debut - timedelta(days=7), fin - timedelta(days=7), service_ids)
    apercu = construire_apercu_hebdo(semaine, precedente)
    await set_cached(redis, cle, apercu.model_dump(mode="json"))
    return apercu


async def apercu_mensuel_distribution(
    db: AsyncSession,
    redis: Redis,
    user: Utilisateur,
    *,
    annee: int,
    mois: int,
    region_id: int | None = None,
) -> ApercuMensuelDistributionResponse:
    _assert_distribution_rapport_role(user)
    region = _resolve_region_id(user, region_id)
    cle = f"rapports:apercu:mensuel:{region or 0}:{annee}:{mois}"
    cached = await get_cached(redis, cle)
    if isinstance(cached, dict) and "services" in cached:
        return ApercuMensuelDistributionResponse.model_validate(cached)
    data = await rapport_mensuel_service.collect_mensuel_distribution_data(
        db, redis, user, annee=annee, mois=mois, region_id=region
    )
    services = [
        ApercuSerie(libelle=s.code or s.libelle, nombre=s.nombre_interruptions, end_mwh=round(s.end_mwh, 3), part_pct=s.part_pct)
        for s in sorted(data.carte_end.services, key=lambda s: -s.end_mwh)
    ] if data.carte_end else []
    apercu = ApercuMensuelDistributionResponse(
        annee=annee,
        mois=mois,
        region_id=region,
        indicateurs=[
            ApercuValeur(libelle="Interruptions", valeur=data.end.aggregate.nombre_interruptions),
            ApercuValeur(libelle="END HTA (MWh)", valeur=round(data.end.aggregate.end_mwh, 3)),
            ApercuValeur(libelle="SAIFI", valeur=round(data.saifi.aggregate.saifi, 4)),
            ApercuValeur(libelle="SAIDI (h)", valeur=round(data.saidi.aggregate.saidi, 4)),
        ],
        services=services,
        top_feeders=[
            ApercuSerie(libelle=f.libelle, nombre=f.nombre_interruptions, end_mwh=round(f.end_mwh, 3))
            for f in data.top_feeders.items
        ],
    )
    await set_cached(redis, cle, apercu.model_dump(mode="json"))
    return apercu
