"""Menu « Suivi incidents » : résolution des filtres communs aux onglets.

Périmètre : même règle que les indicateurs (``indicateurs_service._resolve_scope``) — rôles
nationaux libres, BCC / BRC limités à leur région (``scope_service_id`` = région), SUPERVISEUR
limité à son service. Les valeurs imposées par le rôle remplacent celles de la requête.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import HTTPException, status
from pydantic import ValidationError

from app.core.rbac_helpers import is_superadmin
from app.models.utilisateurs import Utilisateur
from app.schemas.suivi_incidents import (
    FiltresIncidents,
    FiltresResolus,
    PerimetreSuivi,
    SemaineSenelecSchema,
)
from app.services.indicateurs_service import _resolve_scope
from app.services.periodes import semaine_senelec, semaine_senelec_passee


def _hors_perimetre(message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={"status": "error", "data": None, "error": message},
    )


def _invalide(erreur: ValidationError) -> HTTPException:
    messages = "; ".join(str(e.get("msg", "")).removeprefix("Value error, ") for e in erreur.errors())
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail={"status": "error", "data": None, "error": messages or "Filtres invalides"},
    )


def libelle_periode(debut: date, fin: date) -> str:
    """« S47 · 14/11 → 20/11/2026 » pour une semaine SENELEC, « 01/11 → 25/11/2026 » sinon."""
    semaine = semaine_senelec(debut)
    plage = f"{debut:%d/%m} → {fin:%d/%m/%Y}"
    if semaine.debut == debut and semaine.fin == fin:
        return f"S{semaine.numero} · {plage}"
    return plage


def resoudre_filtres(
    user: Utilisateur,
    bruts: dict[str, Any],
    aujourd_hui: date | None = None,
) -> FiltresResolus:
    """Filtres complétés : période par défaut (semaine SENELEC passée), périmètre du rôle."""
    valeurs = {cle: v for cle, v in bruts.items() if v is not None}
    if "debut" not in valeurs or "fin" not in valeurs:
        defaut = semaine_senelec_passee(aujourd_hui or date.today())
        valeurs.setdefault("debut", defaut.debut)
        valeurs.setdefault("fin", defaut.fin)
    try:
        filtres = FiltresIncidents.model_validate(valeurs)
    except ValidationError as erreur:
        raise _invalide(erreur) from erreur

    # Lève 403 hors périmètre (autre région pour un BCC / BRC, région pour un SUPERVISEUR)
    scope = _resolve_scope(user, region_id=filtres.region_id)
    perimetre = PerimetreSuivi(niveau=scope.niveau, scope_id=scope.scope_id)  # type: ignore[arg-type]
    roles = {ur.role.nom for ur in user.user_roles}
    national = is_superadmin(user) or bool(roles & {"ADMIN_SCR", "ADMIN_SAQS"})
    # Région imposée seulement à un compte régional (pas à un national qui choisit une région)
    if scope.niveau == "region" and roles & {"BCC", "BRC"} and not national:
        filtres = filtres.model_copy(update={"region_id": scope.scope_id})
        perimetre.region_verrouillee = True
    elif scope.niveau == "service":
        if filtres.service_id is not None and filtres.service_id != scope.scope_id:
            raise _hors_perimetre("Hors périmètre : service non autorisé pour votre compte")
        filtres = filtres.model_copy(update={"service_id": scope.scope_id})
        perimetre.service_verrouille = True

    semaine = semaine_senelec(filtres.debut)
    est_semaine = semaine.debut == filtres.debut and semaine.fin == filtres.fin
    return FiltresResolus(
        filtres=filtres,
        semaine=SemaineSenelecSchema(**semaine.__dict__) if est_semaine else None,
        libelle_periode=libelle_periode(filtres.debut, filtres.fin),
        perimetre=perimetre,
    )
