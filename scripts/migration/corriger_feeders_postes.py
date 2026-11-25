#!/usr/bin/env python3
"""Corrige le feeder des postes SIRV2 rangés sur un feeder « par défaut » (constat du 23/11/2026).

Constat : 73 % des postes (8 228 sur 11 300) sont sur AIR SENEGAL 30 KV ou SAUVEGARDE.
Origine, dans la table Postes de SIR v1 :
- 6 626 postes portent le texte « AIR SENEGAL 30 KV » et idfeeder = 0 (valeur par défaut de SIR v1) ;
- 1 630 postes portent idfeeder = 30 (SAUVEGARDE) alors que leur texte nomme le vrai feeder (ex. SAII) :
  la reprise a privilégié idfeeder.

Pour chaque poste sans feeder ou sur un feeder par défaut, quatre sources proposent un feeder :
0. exploitants : liste des postes tenue par les exploitants (« LISTE POSTES DAKAR … .xlsx », --liste-exploitants) ;
1. texte   : colonne « feeder » de la table Postes de SIR v1 (si ce n'est pas un feeder par défaut) ;
2. interr. : feeder des interruptions où le poste a été coupé (poste_interruptions, majoritaire à 60 %) ;
3. sig     : feeder du nœud SIG de même nom (nom porté par un seul nœud).
Décision : sources concordantes → « sure » ; majorité d'au moins deux sources → « majoritaire » ; une seule
source → « probable » ; désaccord sans majorité → « a_arbitrer » (non modifié, à traiter dans Administration → Schémas unifilaires → Rapprochement).

Usage (poste SENELEC, accès à la base SIRV2) :
    python scripts/migration/corriger_feeders_postes.py
        → simulation : rapport CSV, rien n'est écrit
    python scripts/migration/corriger_feeders_postes.py --execute [--niveau sure]
        → applique « sure » et « probable » (ou « sure » seulement) ; sauvegarder la base avant.
          Le rapport garde l'ancien feeder de chaque poste modifié.
    python scripts/migration/corriger_feeders_postes.py --restaurer reports/feeders_postes_AAAAMMJJ_HHMM.csv --execute
        → remet l'ancien feeder des postes modifiés par ce rapport
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import scripts.migration._bootstrap  # noqa: F401,E402
from sqlalchemy import text  # noqa: E402

from app.services.schema_unifilaire_rapprochement import cle_poste  # noqa: E402
from scripts.migration.config import get_settings  # noqa: E402
from scripts.migration.db_session import get_session  # noqa: E402

FEEDERS_PAR_DEFAUT = ("AIR SENEGAL 30 KV", "SAUVEGARDE")
PART_MAJORITAIRE = 0.6


def cle_feeder(nom: str | None) -> str:
    texte = unicodedata.normalize("NFKD", nom or "").encode("ascii", "ignore").decode().upper()
    return re.sub(r"[^A-Z0-9]", "", texte)


def feeder_majoritaire(comptes: Counter[int], exclus: set[int]) -> int | None:
    """Feeder le plus fréquent (hors feeders par défaut) s'il représente au moins 60 % des coupures."""
    utiles = Counter({f: n for f, n in comptes.items() if f not in exclus})
    total = sum(utiles.values())
    if not total:
        return None
    feeder, n = utiles.most_common(1)[0]
    return feeder if n / total >= PART_MAJORITAIRE else None


def decider(propositions: dict[str, int | None]) -> tuple[int | None, str]:
    """(feeder retenu, niveau) à partir des propositions {source: feeder_id}.

    sure : au moins deux sources, toutes d'accord ; majoritaire : un feeder porté par au moins deux sources
    et par plus de sources que tout autre ; probable : une seule source ; a_arbitrer : désaccord sans majorité.
    """
    votes = Counter(v for v in propositions.values() if v is not None)
    if not votes:
        return None, "sans_source"
    (premier, n1), *autres = votes.most_common()
    if not autres:
        return premier, ("sure" if n1 >= 2 else "probable")
    if n1 >= 2 and n1 > autres[0][1]:
        return premier, "majoritaire"
    return None, "a_arbitrer"


def lire_liste_exploitants(chemin: Path) -> list[tuple[str, str, str, str]]:
    """Liste des postes tenue par les exploitants (.xlsx) : (service, poste source, feeder, poste).

    Colonnes reconnues par leur en-tête : SERVICES, POSTES SOURCES, FEEDERS, POSTES.
    """
    from openpyxl import load_workbook

    classeur = load_workbook(chemin, read_only=True, data_only=True)
    lignes: list[tuple[str, str, str, str]] = []
    for feuille in classeur.worksheets:
        entete: dict[str, int] | None = None
        for valeurs in feuille.iter_rows(values_only=True):
            cellules = [str(v).strip() if v is not None else "" for v in valeurs]
            if entete is None:
                cles = {cle_feeder(c): i for i, c in enumerate(cellules)}
                if {"FEEDERS", "POSTES"} <= cles.keys():
                    entete = cles
                continue
            def col(nom: str) -> str:
                i = entete.get(nom)  # type: ignore[union-attr]
                return cellules[i] if i is not None and i < len(cellules) else ""
            if col("POSTES") and col("FEEDERS"):
                lignes.append((col("SERVICES"), col("POSTESSOURCES"), col("FEEDERS"), col("POSTES")))
    return lignes


def _texte_sir_v1() -> dict[str, str]:
    """IDPostes (texte) → colonne « feeder » de la table Postes de SIR v1 (export JSONL)."""
    chemin = get_settings().exports_dir / "Postes.jsonl"
    if not chemin.exists():
        print(f"Export SIR v1 absent ({chemin}) : la source « texte » est ignorée.")
        return {}
    resultat: dict[str, str] = {}
    with chemin.open(encoding="utf-8") as f:
        for ligne in f:
            r = json.loads(ligne)
            if r.get("idpostes") is not None and r.get("feeder"):
                resultat[str(int(float(r["idpostes"])))] = str(r["feeder"]).strip()
    return resultat


def _legacy_postes() -> dict[int, str]:
    """id SIRV2 → IDPostes SIR v1 (id_maps/postes.json)."""
    chemin = get_settings().id_maps_dir / "postes.json"
    if not chemin.exists():
        return {}
    donnees = json.loads(chemin.read_text(encoding="utf-8"))
    return {int(v): str(k) for k, v in donnees.items() if str(k).isdigit()}


def restaurer(fichier: Path, executer: bool) -> int:
    with fichier.open(encoding="utf-8-sig") as f:
        lignes = [r for r in csv.DictReader(f, delimiter=";") if r["applique"] == "oui"]
    print(f"{len(lignes)} postes à remettre sur leur ancien feeder.")
    if not executer:
        print("Simulation : relancez avec --execute.")
        return 0
    with get_session() as session:
        for r in lignes:
            session.execute(
                text("UPDATE dbo.postes SET feeder_id = :f WHERE id = :i"),
                {"f": int(r["ancien_feeder_id"]) if r["ancien_feeder_id"] else None, "i": int(r["poste_id"])},
            )
    print("Restauration faite.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--execute", action="store_true", help="écrire en base (sinon simulation)")
    parser.add_argument("--niveau", choices=("sure", "probable"), default="probable",
                        help="sure : seulement les sources concordantes ; probable : aussi majoritaire et source seule")
    parser.add_argument("--liste-exploitants", type=Path,
                        help="liste des postes des exploitants (.xlsx : SERVICES, POSTES SOURCES, FEEDERS, POSTES)")
    parser.add_argument("--tous", action="store_true",
                        help="examiner aussi les postes sur un feeder ordinaire (changés seulement si « sure »)")
    parser.add_argument("--restaurer", type=Path, help="rapport d'une exécution précédente à annuler")
    args = parser.parse_args()
    if args.restaurer:
        return restaurer(args.restaurer, args.execute)

    with get_session() as session:
        feeders = session.execute(
            text("SELECT f.id, f.libelle, f.code, ps.libelle FROM dbo.feeders f"
                 " LEFT JOIN dbo.postes_sources ps ON ps.id = f.poste_source_id WHERE f.is_active = 1")
        ).all()
        nom_feeder = {int(i): lib for i, lib, _, _ in feeders}
        ps_feeder = {int(i): ps for i, _, _, ps in feeders}
        par_cle: dict[str, set[int]] = defaultdict(set)
        for i, lib, code, _ in feeders:
            for nom in (lib, code):
                if cle_feeder(nom):
                    par_cle[cle_feeder(nom)].add(int(i))
        defaut = {i for i, lib, _, _ in feeders if cle_feeder(lib) in {cle_feeder(n) for n in FEEDERS_PAR_DEFAUT}}
        print("Feeders par défaut :", ", ".join(f"{nom_feeder[i]} (id {i})" for i in sorted(defaut)))

        postes = session.execute(
            text("SELECT id, code, libelle, feeder_id FROM dbo.postes WHERE is_active = 1")
        ).all()
        par_defaut = {int(p.id) for p in postes if p.feeder_id is None or int(p.feeder_id) in defaut}
        a_corriger = postes if args.tous else [p for p in postes if int(p.id) in par_defaut]
        print(f"{len(postes)} postes actifs, dont {len(par_defaut)} sans feeder ou sur un feeder par défaut ;"
              f" {len(a_corriger)} examinés.")

        # 1. Liste des exploitants : feeder cherché d'abord parmi ceux de son poste source
        exploitants: dict[str, set[int]] = defaultdict(set)
        if args.liste_exploitants:
            feeders_du_ps: dict[str, dict[str, set[int]]] = defaultdict(lambda: defaultdict(set))
            for i, lib, code, ps in feeders:
                for nom in (lib, code):
                    if cle_feeder(nom):
                        feeders_du_ps[cle_feeder(ps)][cle_feeder(nom)].add(int(i))
            liste = lire_liste_exploitants(args.liste_exploitants)
            inconnus: Counter[str] = Counter()
            for _service, ps, feeder, poste in liste:
                ids = feeders_du_ps.get(cle_feeder(ps), {}).get(cle_feeder(feeder)) or par_cle.get(cle_feeder(feeder), set())
                if len(ids) == 1:
                    exploitants[cle_poste(poste)].add(next(iter(ids)))
                else:
                    inconnus[f"{ps} / {feeder}"] += 1
            print(f"Liste des exploitants : {len(liste)} postes ; feeders non reconnus dans SIRV2 :"
                  f" {sum(inconnus.values())} postes ({len(inconnus)} feeders)")
            for nom, n in inconnus.most_common(15):
                print(f"    {nom} : {n}")

        # 2. Feeders des interruptions où le poste a été coupé (feeder du lien, sinon de l'interruption)
        coupures: dict[int, Counter[int]] = defaultdict(Counter)
        for poste_id, feeder_id, n in session.execute(
            text("SELECT pi.poste_id, COALESCE(pi.feeder_id, i.feeder_id) AS feeder_id, COUNT(*) AS n"
                 " FROM dbo.poste_interruptions pi JOIN dbo.interruptions i ON i.id = pi.interruption_id"
                 " WHERE COALESCE(pi.feeder_id, i.feeder_id) IS NOT NULL"
                 " GROUP BY pi.poste_id, COALESCE(pi.feeder_id, i.feeder_id)")
        ).all():
            coupures[int(poste_id)][int(feeder_id)] += int(n)

        # 3. SIG : nœud de même nom (unique), rattaché à un feeder SIRV2
        sig_par_cle: dict[str, set[int]] = defaultdict(set)
        # Nœuds en service seulement (SIG ArcGIS à la place des nœuds SIR v1 remplacés, migration 5f6a7b8c9d0e)
        actifs = " AND est_actif = 1" if session.execute(
            text("SELECT COL_LENGTH('dbo.noeuds_sig', 'est_actif')")).scalar() is not None else ""
        for nom, feeder_id in session.execute(
            text(f"SELECT nom, feeder_id FROM dbo.noeuds_sig WHERE nom IS NOT NULL{actifs}")
        ).all():
            cle = cle_poste(nom)
            if cle:
                sig_par_cle[cle].add(int(feeder_id) if feeder_id is not None else -1)

    textes = _texte_sir_v1()
    legacy = _legacy_postes()

    lignes: list[dict[str, object]] = []
    for p in a_corriger:
        props: dict[str, int | None] = {"exploitants": None, "texte": None, "interruptions": None, "sig": None}
        expl = exploitants.get(cle_poste(p.libelle), set())
        if len(expl) == 1:
            props["exploitants"] = next(iter(expl))
        texte = textes.get(legacy.get(int(p.id), ""), "")
        ids = par_cle.get(cle_feeder(texte), set())
        if len(ids) == 1 and not ids & defaut:
            props["texte"] = next(iter(ids))
        props["interruptions"] = feeder_majoritaire(coupures.get(int(p.id), Counter()), defaut)
        sig = sig_par_cle.get(cle_poste(p.libelle), set())
        if len(sig) == 1 and next(iter(sig)) not in defaut and next(iter(sig)) != -1:
            props["sig"] = next(iter(sig))
        retenu, niveau = decider(props)
        if int(p.id) not in par_defaut:
            # Poste sur un feeder ordinaire (--tous) : changé seulement si toutes les sources concordent
            if retenu == p.feeder_id or niveau != "sure":
                continue
        lignes.append({
            "poste_id": p.id, "code": p.code, "poste": p.libelle,
            "ancien_feeder_id": p.feeder_id or "", "ancien_feeder": nom_feeder.get(int(p.feeder_id), "") if p.feeder_id else "",
            "texte_sir_v1": texte,
            "feeder_exploitants": nom_feeder.get(props["exploitants"], "") if props["exploitants"] else "",
            "feeder_texte": nom_feeder.get(props["texte"], "") if props["texte"] else "",
            "feeder_interruptions": nom_feeder.get(props["interruptions"], "") if props["interruptions"] else "",
            "feeder_sig": nom_feeder.get(props["sig"], "") if props["sig"] else "",
            "niveau": niveau,
            "nouveau_feeder_id": retenu or "",
            "nouveau_feeder": nom_feeder.get(retenu, "") if retenu else "",
            "poste_source": ps_feeder.get(retenu, "") if retenu else "",
            "applique": "non",
        })

    niveaux = Counter(str(li["niveau"]) for li in lignes)
    print("Propositions :", ", ".join(f"{k} {v}" for k, v in niveaux.most_common()))
    print("Sources :", ", ".join(
        f"{s} {sum(1 for li in lignes if li['feeder_' + s])}" for s in ("exploitants", "texte", "interruptions", "sig")))
    acceptes = {"sure"} if args.niveau == "sure" else {"sure", "majoritaire", "probable"}
    a_appliquer = [li for li in lignes if li["niveau"] in acceptes and li["nouveau_feeder_id"]]
    print(f"À appliquer (niveau {args.niveau}) : {len(a_appliquer)} postes ;"
          f" à arbitrer : {niveaux.get('a_arbitrer', 0)} ; sans source : {niveaux.get('sans_source', 0)}.")

    if args.execute and a_appliquer:
        with get_session() as session:
            for li in a_appliquer:
                session.execute(
                    text("UPDATE dbo.postes SET feeder_id = :f WHERE id = :i"),
                    {"f": int(li["nouveau_feeder_id"]), "i": int(li["poste_id"])},
                )
                li["applique"] = "oui"
            # même transaction : tout ou rien
        print(f"{len(a_appliquer)} postes mis à jour.")

    rapport = get_settings().reports_dir / f"feeders_postes_{datetime.now():%Y%m%d_%H%M}.csv"
    rapport.parent.mkdir(parents=True, exist_ok=True)
    with rapport.open("w", encoding="utf-8-sig", newline="") as f:
        ecrivain = csv.DictWriter(f, fieldnames=list(lignes[0].keys()) if lignes else ["poste_id"], delimiter=";")
        ecrivain.writeheader()
        ecrivain.writerows(lignes)
    print(f"Rapport : {rapport}")
    if not args.execute:
        print("Simulation : rien n'a été écrit. Relancez avec --execute après une sauvegarde de la base.")
    return 0


if __name__ == "__main__":
    from scripts.migration._bootstrap import terminer

    terminer(main())
