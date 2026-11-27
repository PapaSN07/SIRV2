#!/usr/bin/env python3
"""Crée dans SIRV2 les départs (feeders) marqués « créer » dans le classeur des départs manquants validé.

Pour chaque ligne DÉCISION = créer : poste source SIRV2 retrouvé par son nom (exact, puis le plus proche),
service et région repris des autres feeders de ce poste source (le plus fréquent), code unique de 20
caractères au plus tiré du nom. Les lignes « existant » sont lues par corriger_feeders_postes.py et
import_sig_arcgis.py (option --correspondances) ; les lignes sans décision ou « à préciser » sont listées.

Simulation par défaut ; --execute écrit en base (sauvegarder la base avant).

Usage (poste SENELEC) :
    python scripts/migration/creer_departs_manquants.py --classeur "scripts\\migration\\reports\\departs_manquants_propositions.xlsx"
"""

from __future__ import annotations

import argparse
import difflib
import re
import sys
from collections import Counter
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import scripts.migration._bootstrap  # noqa: F401,E402

try:
    from scripts.migration.corriger_feeders_postes import cle_feeder
except ModuleNotFoundError:  # copie posée à côté de corriger_feeders_postes.py
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from corriger_feeders_postes import cle_feeder  # type: ignore[no-redef]

LONGUEUR_CODE = 20


def lire_decisions(chemin: Path) -> list[dict[str, str]]:
    """Lignes du classeur : poste source, départ, décision (minuscules, sans accent sur « créer »)."""
    from openpyxl import load_workbook

    feuille = load_workbook(chemin, read_only=True, data_only=True).worksheets[0]
    lignes = list(feuille.iter_rows(values_only=True))
    entete = [cle_feeder(str(c or "")) for c in lignes[0]]
    i_ps = entete.index("POSTESOURCE")
    i_dep = entete.index("DEPARTNOMRELEVE")
    i_dec = next(i for i, c in enumerate(entete) if c.startswith("DECISION"))
    resultat = []
    for ligne in lignes[1:]:
        if not ligne[i_dep]:
            continue
        decision = str(ligne[i_dec] or "").strip().lower().replace("é", "e")
        resultat.append({"ps": str(ligne[i_ps] or "").strip(), "depart": str(ligne[i_dep]).strip(),
                         "decision": decision})
    return resultat


def code_unique(libelle: str, existants: set[str]) -> str:
    """Code du feeder : nom en majuscules sans accents ni ponctuation, tronqué, suffixé si déjà pris."""
    base = re.sub(r"[^A-Z0-9 ]", " ", _ascii(libelle).upper()).strip()
    base = re.sub(r"\s+", " ", base)[:LONGUEUR_CODE].strip() or "DEPART"
    code, n = base, 2
    while code.upper() in existants:
        suffixe = f" {n}"
        code = base[: LONGUEUR_CODE - len(suffixe)].strip() + suffixe
        n += 1
    existants.add(code.upper())
    return code


def _ascii(texte: str) -> str:
    import unicodedata

    return "".join(c for c in unicodedata.normalize("NFD", texte) if unicodedata.category(c) != "Mn")


def trouver_poste_source(nom: str, postes_sources: dict[int, str]) -> int | None:
    """Poste source SIRV2 par nom : égalité des clés, puis inclusion unique, puis le plus proche (≥ 0,8)."""
    cle = cle_feeder(nom)
    par_cle = {cle_feeder(lib): i for i, lib in postes_sources.items()}
    if cle in par_cle:
        return par_cle[cle]
    inclus = [i for k, i in par_cle.items() if cle and cle in k]
    if len(inclus) == 1:
        return inclus[0]
    proche = difflib.get_close_matches(cle, list(par_cle), n=1, cutoff=0.8)
    return par_cle[proche[0]] if proche else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--classeur", type=Path, required=True)
    parser.add_argument("--execute", action="store_true", help="écrire en base (sauvegarder la base avant)")
    args = parser.parse_args()

    from sqlalchemy import text

    from scripts.migration.db_session import get_session

    decisions = lire_decisions(args.classeur)
    a_creer = [d for d in decisions if d["decision"] == "creer"]
    en_attente = [d for d in decisions if d["decision"] not in ("creer", "existant")]
    print(f"Classeur : {len(decisions)} départs — {len(a_creer)} à créer, "
          f"{sum(d['decision'] == 'existant' for d in decisions)} existants, {len(en_attente)} sans décision.")

    with get_session() as session:
        postes_sources = {int(i): lib or code or "" for i, code, lib in session.execute(text(
            "SELECT id, code, libelle FROM dbo.postes_sources WHERE is_active = 1")).all()}
        feeders = session.execute(text(
            "SELECT id, code, libelle, poste_source_id, service_id, region_id FROM dbo.feeders")).all()
        codes = {str(f.code).upper() for f in feeders}
        cles_existantes = {(int(f.poste_source_id), cle_feeder(f.libelle)) for f in feeders}

        creations = []
        for d in a_creer:
            ps_id = trouver_poste_source(d["ps"], postes_sources)
            if ps_id is None:
                print(f"  ✗ {d['depart']} : poste source « {d['ps']} » introuvable dans SIRV2 — non créé")
                continue
            if (ps_id, cle_feeder(d["depart"])) in cles_existantes:
                print(f"  = {d['depart']} existe déjà sur {postes_sources[ps_id]} — rien à faire")
                continue
            voisins = [f for f in feeders if int(f.poste_source_id) == ps_id]
            service = Counter(f.service_id for f in voisins if f.service_id).most_common(1)
            region = Counter(f.region_id for f in voisins if f.region_id).most_common(1)
            creation = {"ps": ps_id, "libelle": d["depart"].upper(), "code": code_unique(d["depart"], codes),
                        "service": service[0][0] if service else None,
                        "region": region[0][0] if region else None}
            creations.append(creation)
            print(f"  + {creation['libelle']} (code {creation['code']}) sur {postes_sources[ps_id]} "
                  f"(id {ps_id}), service {creation['service'] or '—'}, région {creation['region'] or '—'}")

        if en_attente:
            print("Sans décision (non traités) :")
            for d in en_attente:
                print(f"  ? {d['ps']} / {d['depart']}")

        if not args.execute:
            print(f"SIMULATION : {len(creations)} feeders seraient créés. Relancer avec --execute après sauvegarde.")
            return 0
        for c in creations:
            session.execute(text(
                "INSERT INTO dbo.feeders (poste_source_id, service_id, region_id, code, libelle, is_active)"
                " VALUES (:ps, :service, :region, :code, :libelle, 1)"), c)
        session.commit()
        print(f"{len(creations)} feeders créés.")
    return 0


if __name__ == "__main__":
    from scripts.migration._bootstrap import terminer

    terminer(main())
