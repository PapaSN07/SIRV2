"""Entrées du Référentiel probablement créées par l'ancien import FIS (lecture seule).

Avant le correctif du 25/11/2026, l'import FIS (ouvert au BCC) créait une nature, une cause
ou un siège pour tout code absent, avec le libellé du fichier : codes des tables de
correspondance de `fis_import_service` (AGRESSION, INC_HTA, CABLE…) et replis AUTRE / INCONNUE
(les natures FIS PERMANENT, FUGITIF… sont seedées et ne sont pas listées).
Les codes repris de SIR v1 ont une autre forme (préfixe « D » : DAGRESSION…).

Le script liste ces entrées avec le nombre d'interruptions qui les utilisent. Il ne modifie
rien : la décision (garder, désactiver, ou rattacher les interruptions à l'entrée SIR v1
équivalente puis désactiver) revient à l'Admin SCR, depuis l'écran Référentiel.

Usage (poste SENELEC, sous VPN) :
    docker compose exec api python -m scripts.diag_referentiel_fis
"""

from __future__ import annotations

import asyncio

from sqlalchemy import func, select

from app.core.database import AsyncSessionLocal, engine
from app.models.interruptions import Interruption
from app.models.referentiel import Cause, Nature, Siege
from app.services.fis_import_service import (
    CAUSE_LIBELLE_TO_CODE,
    NATURE_LIBELLE_TO_CODE,
    SIEGE_LIBELLE_TO_CODE,
)

_CODES = {
    # Les natures FIS sont seedées (seed_natures) : seul le repli AUTRE vient de l'import
    "Natures": (Nature, Interruption.nature_id, {"AUTRE"} - set(NATURE_LIBELLE_TO_CODE.values())),
    "Causes": (Cause, Interruption.cause_id, {code for code, _ in CAUSE_LIBELLE_TO_CODE.values()} | {"INCONNUE"}),
    "Sièges": (Siege, Interruption.siege_id, {*SIEGE_LIBELLE_TO_CODE.values(), "AUTRE"}),
}


async def main() -> None:
    engine.echo = False
    total = 0
    async with AsyncSessionLocal() as db:
        for titre, (modele, colonne_fk, codes) in _CODES.items():
            colonnes = [modele.id, modele.code, modele.libelle, modele.is_active]
            if hasattr(modele, "type_reseau"):
                colonnes.append(modele.type_reseau)
            requete = (
                select(*colonnes, func.count(Interruption.id).label("nb"))
                .outerjoin(Interruption, colonne_fk == modele.id)
                .where(modele.code.in_(sorted(codes)))
                .group_by(*colonnes)
                .order_by(modele.code)
            )
            lignes = (await db.execute(requete)).all()
            print(f"\n{titre} : {len(lignes)} entrée(s) au code de l'import FIS")
            for ligne in lignes:
                etat = "active" if ligne.is_active else "inactive"
                reseau = f" · {ligne.type_reseau}" if hasattr(ligne, "type_reseau") else ""
                print(f"  #{ligne.id} {ligne.code:<14} « {ligne.libelle} » ({etat}{reseau}) — {ligne.nb} interruption(s)")
            total += len(lignes)
    await engine.dispose()
    if total == 0:
        print("\nAucune entrée créée par l'ancien import FIS.")
    else:
        print("\nÀ examiner par l'Admin SCR (Référentiel) : ces entrées n'ont été créées par aucun seed ni aucune migration.")


if __name__ == "__main__":
    asyncio.run(main())
