"""Diagnostic (lecture seule) des données réseau distribution chargées dans SIRV2.

Vérifie que chaque relation utilisée par la saisie d'une interruption existe :
région → poste source → feeder → sous-feeder → postes, et feeder → tronçons SIG.

Usage (depuis le dossier SIRV2, conteneur API démarré) :
    docker compose exec api python -m scripts.diag_reseau
    docker compose exec api python -m scripts.diag_reseau --feeder "HANN 30KV"
"""

from __future__ import annotations

import argparse
import asyncio
from typing import Any

from sqlalchemy import text

from app.core.database import AsyncSessionLocal

# (libellé, requête qui renvoie un seul nombre, est-ce un problème si > 0 ?)
_CONTROLES: list[tuple[str, str, bool]] = [
    ("Régions", "SELECT COUNT(*) FROM dbo.regions", False),
    ("Postes sources actifs", "SELECT COUNT(*) FROM dbo.postes_sources WHERE is_active = 1", False),
    (
        "  … sans région (invisibles dans la liste par région)",
        """SELECT COUNT(*) FROM dbo.postes_sources ps
           WHERE ps.is_active = 1 AND ps.region_id IS NULL
             AND NOT EXISTS (
               SELECT 1 FROM dbo.feeders f JOIN dbo.services s ON s.id = f.service_id
               WHERE f.poste_source_id = ps.id AND s.region_id IS NOT NULL)""",
        True,
    ),
    (
        "  … sans aucun feeder",
        """SELECT COUNT(*) FROM dbo.postes_sources ps WHERE ps.is_active = 1
           AND NOT EXISTS (SELECT 1 FROM dbo.feeders f WHERE f.poste_source_id = ps.id AND f.is_active = 1)""",
        True,
    ),
    (
        "  … dont tous les feeders sont dans une autre région (région du poste source à vérifier)",
        """SELECT COUNT(*) FROM dbo.postes_sources ps
           WHERE ps.is_active = 1 AND ps.region_id IS NOT NULL
             AND EXISTS (SELECT 1 FROM dbo.feeders f JOIN dbo.services s ON s.id = f.service_id
                         WHERE f.poste_source_id = ps.id AND f.is_active = 1)
             AND NOT EXISTS (SELECT 1 FROM dbo.feeders f JOIN dbo.services s ON s.id = f.service_id
                             WHERE f.poste_source_id = ps.id AND f.is_active = 1 AND s.region_id = ps.region_id)""",
        True,
    ),
    ("Feeders actifs", "SELECT COUNT(*) FROM dbo.feeders WHERE is_active = 1", False),
    (
        "  … sans service",
        "SELECT COUNT(*) FROM dbo.feeders WHERE is_active = 1 AND service_id IS NULL",
        True,
    ),
    (
        "  … avec au moins un sous-feeder",
        """SELECT COUNT(DISTINCT sf.feeder_id) FROM dbo.sous_feeders sf
           JOIN dbo.feeders f ON f.id = sf.feeder_id WHERE f.is_active = 1 AND sf.is_active = 1""",
        False,
    ),
    (
        "  … sans aucun poste rattaché (liste « Postes impactés » vide)",
        """SELECT COUNT(*) FROM dbo.feeders f WHERE f.is_active = 1
           AND NOT EXISTS (SELECT 1 FROM dbo.postes p WHERE p.feeder_id = f.id AND p.is_active = 1)""",
        True,
    ),
    (
        "  … sans tronçon SIG rattaché par identifiant",
        """SELECT COUNT(*) FROM dbo.feeders f WHERE f.is_active = 1
           AND NOT EXISTS (SELECT 1 FROM dbo.troncons_sig t WHERE t.feeder_id = f.id)""",
        True,
    ),
    ("Sous-feeders actifs", "SELECT COUNT(*) FROM dbo.sous_feeders WHERE is_active = 1", False),
    ("Postes MT/BT actifs", "SELECT COUNT(*) FROM dbo.postes WHERE is_active = 1", False),
    (
        "  … sans feeder",
        "SELECT COUNT(*) FROM dbo.postes WHERE is_active = 1 AND feeder_id IS NULL",
        True,
    ),
    (
        "  … sans feeder mais déjà impactés sur un feeder (rattachables, voir backfill)",
        """SELECT COUNT(DISTINCT p.id) FROM dbo.postes p
           JOIN dbo.poste_interruptions pi ON pi.poste_id = p.id
           WHERE p.is_active = 1 AND p.feeder_id IS NULL AND pi.feeder_id IS NOT NULL""",
        True,
    ),
    ("Tronçons SIG", "SELECT COUNT(*) FROM dbo.troncons_sig", False),
    (
        "  … chargements SIG distincts (date_chargement)",
        "SELECT COUNT(DISTINCT date_chargement) FROM dbo.troncons_sig",
        False,
    ),
    (
        "  … sans feeder_id (rattachés seulement par le nom du départ)",
        "SELECT COUNT(*) FROM dbo.troncons_sig WHERE feeder_id IS NULL",
        True,
    ),
    (
        "Interruptions distribution des 30 derniers jours",
        """SELECT COUNT(*) FROM dbo.interruptions
           WHERE type_direction = N'distribution' AND date_apparition >= DATEADD(day, -30, GETDATE())""",
        False,
    ),
    (
        "  … sans aucun poste impacté coché",
        """SELECT COUNT(*) FROM dbo.interruptions i
           WHERE i.type_direction = N'distribution' AND i.date_apparition >= DATEADD(day, -30, GETDATE())
             AND NOT EXISTS (SELECT 1 FROM dbo.poste_interruptions pi WHERE pi.interruption_id = i.id)""",
        True,
    ),
]

_PAR_REGION = """
SELECT r.libelle,
       COUNT(DISTINCT ps.id) AS postes_sources,
       COUNT(DISTINCT f.id) AS feeders,
       COUNT(DISTINCT sf.id) AS sous_feeders,
       COUNT(DISTINCT p.id) AS postes
FROM dbo.regions r
LEFT JOIN dbo.postes_sources ps ON ps.region_id = r.id AND ps.is_active = 1
LEFT JOIN dbo.feeders f ON f.poste_source_id = ps.id AND f.is_active = 1
LEFT JOIN dbo.sous_feeders sf ON sf.feeder_id = f.id AND sf.is_active = 1
LEFT JOIN dbo.postes p ON p.feeder_id = f.id AND p.is_active = 1
GROUP BY r.libelle
ORDER BY r.libelle
"""

_FEEDER = """
SELECT f.id, f.code, f.libelle, f.tension_kv, ps.libelle AS poste_source, s.libelle AS service,
       (SELECT COUNT(*) FROM dbo.sous_feeders sf WHERE sf.feeder_id = f.id AND sf.is_active = 1) AS sous_feeders,
       (SELECT COUNT(*) FROM dbo.postes p WHERE p.feeder_id = f.id AND p.is_active = 1) AS postes,
       (SELECT COUNT(*) FROM dbo.troncons_sig t WHERE t.feeder_id = f.id) AS troncons_sig_par_id,
       (SELECT COUNT(DISTINCT t.date_chargement) FROM dbo.troncons_sig t WHERE t.feeder_id = f.id)
           AS chargements_sig
FROM dbo.feeders f
JOIN dbo.postes_sources ps ON ps.id = f.poste_source_id
LEFT JOIN dbo.services s ON s.id = f.service_id
WHERE f.libelle LIKE :motif OR f.code LIKE :motif
ORDER BY f.libelle
"""


async def _scalar(db: Any, sql: str) -> int:
    return int((await db.execute(text(sql))).scalar_one() or 0)


async def main(feeder: str | None) -> None:
    async with AsyncSessionLocal() as db:
        print("\n=== Contrôle des données réseau SIRV2 (lecture seule) ===\n")
        for libelle, sql, alerte in _CONTROLES:
            try:
                n = await _scalar(db, sql)
            except Exception as exc:  # table absente, colonne manquante…
                print(f"{libelle:<78} ERREUR : {str(exc).splitlines()[0][:80]}")
                continue
            marque = "  ⚠" if alerte and n > 0 else ""
            print(f"{libelle:<78} {n:>8}{marque}")

        print("\n--- Par région (poste source rattaché directement à la région) ---")
        rows = (await db.execute(text(_PAR_REGION))).all()
        print(f"{'Région':<28}{'Postes src':>11}{'Feeders':>9}{'Ss-feed.':>9}{'Postes':>9}")
        for r in rows:
            print(f"{(r[0] or '')[:27]:<28}{r[1]:>11}{r[2]:>9}{r[3]:>9}{r[4]:>9}")

        if feeder:
            print(f"\n--- Feeder(s) correspondant à « {feeder} » ---")
            for r in (await db.execute(text(_FEEDER), {"motif": f"%{feeder}%"})).mappings():
                print(dict(r))
        print("\n⚠ = relation manquante à compléter (référentiel ou script de rattachement).\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--feeder", help="Détail d'un feeder (code ou libellé, recherche partielle)")
    asyncio.run(main(parser.parse_args().feeder))
