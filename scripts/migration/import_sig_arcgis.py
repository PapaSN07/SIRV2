#!/usr/bin/env python3
"""Mise à jour du SIG de SIRV2 depuis un export KMZ ArcGIS (« DAKAR HTA.mxd.kmz », validé SENELEC).

Le KMZ contient trois couches :
- PosteHTABT          → noeuds_sig (source arcgis) : nom, FeederID, PosteSource, puissance, coordonnées
                        X/Y_Centroide (UTM 28N, comme le SIG de SIR v1), zone de responsabilité, statut ;
- CableSouterrainHTA  → troncons_sig (source arcgis) : départ, amont / aval, longueur, section, câble ;
- ConducteurAerienHTA → troncons_sig (source arcgis), idem pour l'aérien.

Règles :
- clé de mise à jour = GlobalID ArcGIS ; un objet nouveau reçoit un legacy_id négatif ;
- un nœud SIR v1 du même poste (même nom, à moins de 2 km) est remplacé : est_actif = 0 ;
  un nœud ArcGIS absent du nouvel export passe aussi à est_actif = 0 ;
- tronçons : date_chargement = date de l'import, donc ils deviennent le « dernier chargement » de leur
  départ (les tronçons SIR v1 du même départ ne sont plus comptés dans les longueurs) ;
- longueur : géométrie quand elle est lisible (aérien), sinon le champ « Longueur mesurée » (km sous 20, m
  au-delà) ; la géométrie de 3 025 câbles et des postes est illisible dans le KML (coordonnées hors Sénégal).

Usage (poste SENELEC) :
    python scripts/migration/import_sig_arcgis.py "D:\\Senelec\\SIRV2\\DAKAR HTA.mxd.kmz" --excel "D:\\Senelec\\SIRV2\\POSTES DAKAR.xls"
    python scripts/migration/import_sig_arcgis.py "D:\\Senelec\\SIRV2\\DAKAR HTA.mxd.kmz"            # simulation
    python scripts/migration/import_sig_arcgis.py "D:\\Senelec\\SIRV2\\DAKAR HTA.mxd.kmz" --execute  # après sauvegarde
"""

from __future__ import annotations

import argparse
import csv
import html
import math
import re
import sys
import unicodedata
import zipfile
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

K = "{http://www.opengis.net/kml/2.2}"
_LIGNE = re.compile(r"<tr[^>]*>\s*<td>(.*?)</td>\s*<td>(.*?)</td>\s*</tr>", re.S)
COUCHE_POSTES = "PosteHTABT"
COUCHES_TRONCONS = {"CableSouterrainHTA": "souterrain", "ConducteurAerienHTA": "aerien"}
DISTANCE_REMPLACEMENT_M = 2000.0


# ── Lecture du KMZ (fonctions pures, testées) ───────────────────────────────────


def _valeur(texte: str) -> str | None:
    v = html.unescape(re.sub(r"<[^>]+>", "", texte)).strip()
    return None if v in ("", "<Nul>") else v


def attributs_description(description: str | None) -> dict[str, str | None]:
    """Tableau clé / valeur de la bulle ArcGIS (description HTML du Placemark)."""
    if not description:
        return {}
    return {_valeur(k) or "": _valeur(v) for k, v in _LIGNE.findall(description)}


def _nombre(valeur: str | None) -> float | None:
    if valeur is None:
        return None
    try:
        return float(valeur.replace(" ", "").replace(",", "."))
    except ValueError:
        return None


def _date(valeur: str | None) -> datetime | None:
    for fmt in ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y"):
        try:
            return datetime.strptime(valeur or "", fmt)
        except ValueError:
            continue
    return None


def geometrie_valide(lignes: list[list[tuple[float, float]]]) -> bool:
    return bool(lignes) and all(12 < y < 17 and -18 < x < -11 for pts in lignes for x, y in pts)


def longueur_geometrie_m(lignes: list[list[tuple[float, float]]]) -> float:
    total = 0.0
    for pts in lignes:
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
            total += 6371000 * math.hypot(
                math.radians(x2 - x1) * math.cos(math.radians((y1 + y2) / 2)), math.radians(y2 - y1)
            )
    return total


SEUIL_CHAMP_EN_METRES = 20.0


def longueur_troncon_m(a: dict[str, str | None], lignes: list[list[tuple[float, float]]], type_ligne: str) -> float | None:
    """Longueur en mètres : la géométrie quand elle est lisible, sinon le champ « Longueur mesurée ».

    Le champ mélange les unités (médiane 0,77 pour les câbles = km, mais 753 valeurs de 30 à 10 000 = m) :
    une valeur de 20 ou plus est lue en mètres, en dessous en kilomètres.
    """
    if geometrie_valide(lignes):
        return round(longueur_geometrie_m(lignes), 3)
    champ = _nombre(a.get("Longueur mesurée, [m]"))
    if champ is None or champ <= 0:
        return None
    return round(champ if champ >= SEUIL_CHAMP_EN_METRES else champ * 1000, 3)


def noeud_arcgis(a: dict[str, str | None]) -> dict[str, object] | None:
    if not a.get("GlobalID") or not a.get("Nom Du Poste"):
        return None
    etat = (a.get("Indicateur d'état") or "").strip().upper()
    return {
        "global_id": a["GlobalID"].strip("{}").upper(),
        "nom": a["Nom Du Poste"].strip()[:255],
        "nom_feeder": (a.get("FeederID") or "").strip()[:255] or None,
        "station": (a.get("PosteSource") or "").strip()[:255] or None,
        "poste_source": (a.get("PosteSource") or "").strip()[:255] or None,
        "coord_x": _nombre(a.get("X_Centroide")),
        "coord_y": _nombre(a.get("Y_Centroide")),
        "delegation": (a.get("Zone de responsabilité") or "").strip()[:100] or None,
        "region": "DAKAR",
        "puissance": (a.get("Puissance Assignée, [KVA]") or "").strip()[:50] or None,
        "famille_poste": (a.get("TypeTransformateur") or a.get("Structure Du Poste") or "").strip()[:100] or None,
        "cellule": (a.get("Nature cellules") or "").strip()[:100] or None,
        "statut_validation": (a.get("Statut de validation") or "").strip()[:30] or None,
        "est_actif": etat not in ("HORS SERVICE", "ABANDONNE", "DEMANTELE"),
        "date_maj": _date(a.get("last_edited_date")),
    }


def troncon_arcgis(a: dict[str, str | None], lignes: list[list[tuple[float, float]]], type_ligne: str) -> dict[str, object] | None:
    if not a.get("GlobalID"):
        return None
    nature = " ".join(x for x in (a.get("Type Du Conducteur") or a.get("Type De Cable"), a.get("Nature de l'âme")) if x)
    return {
        "global_id": a["GlobalID"].strip("{}").upper(),
        "nom_feeder": (a.get("Nom Du Depart") or a.get("NomDepart_Temp") or "").strip()[:255] or None,
        "nom_troncon": (a.get("NomTroncon") or a.get("Nom du Troncon") or "").strip()[:255] or None,
        "nom_noeud_amont": (a.get("Amont") or a.get("Origine") or "").strip()[:255] or None,
        "nom_noeud_aval": (a.get("Aval") or a.get("Destination") or "").strip()[:255] or None,
        "tension_kv": _nombre(a.get("Tension Nominale")),
        "longueur_m": longueur_troncon_m(a, lignes, type_ligne),
        "section": (a.get("Section, [mm2]") or "").strip()[:100] or None,
        "poste_source": (a.get("PosteSource") or "").strip()[:255] or None,
        "type_conducteur": f"{'Souterrain' if type_ligne == 'souterrain' else 'Aérien'} {nature}".strip()[:100],
        "delegation": (a.get("Zone de responsabilité") or "").strip()[:100] or None,
        "date_maj": _date(a.get("last_edited_date")),
    }


def lire_kmz(chemin: Path) -> dict[str, list[tuple[dict[str, str | None], list[list[tuple[float, float]]]]]]:
    """{couche: [(attributs, géométrie)]} — géométrie : listes de (lon, lat)."""
    with zipfile.ZipFile(chemin) as z:
        nom_kml = next(n for n in z.namelist() if n.lower().endswith(".kml"))
        racine = ElementTree.fromstring(z.read(nom_kml))
    couches: dict[str, list[tuple[dict[str, str | None], list[list[tuple[float, float]]]]]] = defaultdict(list)
    for dossier in racine.iter(K + "Folder"):
        nom = dossier.findtext(K + "name") or ""
        for p in dossier.findall(K + "Placemark"):
            lignes = []
            for c in p.iter(K + "coordinates"):
                pts = []
                for xyz in (c.text or "").split():
                    morceaux = xyz.split(",")
                    if len(morceaux) >= 2:
                        pts.append((float(morceaux[0]), float(morceaux[1])))
                lignes.append(pts)
            couches[nom].append((attributs_description(p.findtext(K + "description")), lignes))
    return couches


def enrichir_par_excel(noeuds: list[dict[str, object]], chemin: Path) -> tuple[int, int]:
    """Complète les postes du KMZ avec l'export Excel de la même couche (« POSTES DAKAR.xls »).

    Appariement par le centroïde (X, Y à 0,1 m près : même export ArcGIS). L'Excel apporte l'unité
    d'exploitation (UED…), rangée dans `delegation` (la zone de responsabilité du KMZ, DRD…, à défaut),
    et la structure du poste. Renvoie (postes appariés, lignes Excel sans poste dans le KMZ).
    """
    import pandas as pd

    df = pd.read_excel(chemin)
    colonnes = {cle_feeder(c): c for c in df.columns}
    cx, cy = colonnes.get("XCENTROID"), colonnes.get("YCENTROID")
    if cx is None or cy is None:
        raise ValueError(f"{chemin.name} : colonnes X_Centroid / Y_Centroid introuvables")
    ued, structure = colonnes.get("UNITEDEXPLOITATION"), colonnes.get("STRUCTURED")
    par_xy = {
        (round(float(n["coord_x"]), 1), round(float(n["coord_y"]), 1)): n  # type: ignore[arg-type]
        for n in noeuds if n["coord_x"] and n["coord_y"]
    }
    apparies = orphelins = 0
    for ligne in df.to_dict("records"):
        try:
            n = par_xy.get((round(float(ligne[cx]), 1), round(float(ligne[cy]), 1)))
        except (TypeError, ValueError):
            n = None
        if n is None:
            orphelins += 1
            continue
        apparies += 1
        if ued and isinstance(ligne.get(ued), str) and ligne[ued].strip():
            n["delegation"] = ligne[ued].strip()[:100]
        if structure and isinstance(ligne.get(structure), str) and ligne[structure].strip() and not n["famille_poste"]:
            n["famille_poste"] = ligne[structure].strip()[:100]
    return apparies, orphelins


def cle_feeder(nom: str | None) -> str:
    texte = unicodedata.normalize("NFKD", nom or "").encode("ascii", "ignore").decode().upper()
    return re.sub(r"[^A-Z0-9]", "", texte)


# ── Base ────────────────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("kmz", type=Path)
    parser.add_argument("--excel", type=Path, help="export Excel des postes (« POSTES DAKAR.xls ») : unité d'exploitation")
    parser.add_argument("--execute", action="store_true", help="écrire en base (sinon simulation)")
    args = parser.parse_args()

    import scripts.migration._bootstrap  # noqa: F401
    from sqlalchemy import text

    from app.repositories.sig_admin_repository import RECALCUL_DERNIER_CHARGEMENT
    from app.services.schema_unifilaire_rapprochement import cle_poste
    from scripts.migration.config import get_settings
    from scripts.migration.db_session import get_session

    print(f"Lecture de {args.kmz}…")
    couches = lire_kmz(args.kmz)
    noeuds = [n for a, _ in couches.get(COUCHE_POSTES, []) if (n := noeud_arcgis(a))]
    troncons = [
        t for couche, type_ligne in COUCHES_TRONCONS.items()
        for a, g in couches.get(couche, []) if (t := troncon_arcgis(a, g, type_ligne))
    ]
    longueur_km = sum(float(t["longueur_m"] or 0) for t in troncons) / 1000
    print(f"  {len(noeuds)} postes, {len(troncons)} tronçons ({longueur_km:.1f} km)")
    if args.excel:
        apparies, orphelins = enrichir_par_excel(noeuds, args.excel)
        print(f"  Excel {args.excel.name} : {apparies} postes complétés (unité d'exploitation), {orphelins} lignes sans poste dans le KMZ")

    with get_session() as session:
        migre = session.execute(text("SELECT COL_LENGTH('dbo.noeuds_sig', 'global_id')")).scalar() is not None
        if not migre:
            if args.execute:
                print("La migration 5f6a7b8c9d0e n'est pas appliquée : alembic upgrade head sur le serveur d'abord.")
                return 1
            print("(Migration 5f6a7b8c9d0e pas encore appliquée : simulation comme un premier import.)")
        try:
            from scripts.migration.corriger_feeders_postes import resoudre_feeder
        except ModuleNotFoundError:  # copie du script posée à côté de corriger_feeders_postes.py
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            from corriger_feeders_postes import resoudre_feeder  # type: ignore[no-redef]

        feeders = session.execute(text(
            "SELECT f.id, f.libelle, f.code, ps.libelle FROM dbo.feeders f"
            " LEFT JOIN dbo.postes_sources ps ON ps.id = f.poste_source_id WHERE f.is_active = 1")).all()
        par_cle: dict[str, set[int]] = defaultdict(set)
        feeders_du_ps: dict[str, dict[str, set[int]]] = defaultdict(lambda: defaultdict(set))
        for i, lib, code, ps in feeders:
            for nom in (lib, code):
                if cle_feeder(nom):
                    par_cle[cle_feeder(nom)].add(int(i))
                    feeders_du_ps[cle_feeder(ps)][cle_feeder(nom)].add(int(i))

        def feeder_id(nom: object, poste_source: object = None) -> int | None:
            """Nom du départ ArcGIS → feeder SIRV2 (exact, puis proche dans le poste source)."""
            return resoudre_feeder(str(nom or ""), str(poste_source or ""), feeders_du_ps, par_cle)

        for x in noeuds + troncons:
            x["feeder_id"] = feeder_id(x["nom_feeder"], x.get("poste_source"))
        non_resolus = Counter(str(x["nom_feeder"]) for x in noeuds + troncons if x["nom_feeder"] and x["feeder_id"] is None)

        existants_n = {g: (i, lid) for g, i, lid in session.execute(
            text("SELECT global_id, id, legacy_id FROM dbo.noeuds_sig WHERE global_id IS NOT NULL")).all()} if migre else {}
        existants_t = {g: (i, lid) for g, i, lid in session.execute(
            text("SELECT global_id, id, legacy_id FROM dbo.troncons_sig WHERE global_id IS NOT NULL")).all()} if migre else {}
        min_n = min(0, session.execute(text("SELECT MIN(legacy_id) FROM dbo.noeuds_sig")).scalar() or 0)
        min_t = min(0, session.execute(text("SELECT MIN(legacy_id) FROM dbo.troncons_sig")).scalar() or 0)

        # Nœuds SIR v1 remplacés : même nom et à moins de 2 km d'un poste ArcGIS
        arcgis_par_cle: dict[str, list[tuple[float, float]]] = defaultdict(list)
        for n in noeuds:
            if n["coord_x"] and n["coord_y"]:
                arcgis_par_cle[cle_poste(str(n["nom"]))].append((float(n["coord_x"]), float(n["coord_y"])))  # type: ignore[arg-type]
        remplaces = []
        filtre = "source = 'sir_v1' AND est_actif = 1 AND " if migre else ""
        for i, nom, x, y in session.execute(text(
            "SELECT id, nom, coord_x, coord_y FROM dbo.noeuds_sig"
            f" WHERE {filtre}nom IS NOT NULL AND coord_x > 0 AND coord_y > 0")).all():
            for ax, ay in arcgis_par_cle.get(cle_poste(nom), []):
                if math.hypot(ax - float(x), ay - float(y)) <= DISTANCE_REMPLACEMENT_M:
                    remplaces.append(int(i))
                    break
        dans_export = {n["global_id"] for n in noeuds}
        retires = [i for g, (i, _) in existants_n.items() if g not in dans_export]

        nouveaux_n = sum(1 for n in noeuds if n["global_id"] not in existants_n)
        nouveaux_t = sum(1 for t in troncons if t["global_id"] not in existants_t)
        print(f"Postes : {nouveaux_n} nouveaux, {len(noeuds) - nouveaux_n} mis à jour, {len(retires)} retirés du SIG ;"
              f" {len(remplaces)} nœuds SIR v1 remplacés (même poste)")
        print(f"Tronçons : {nouveaux_t} nouveaux, {len(troncons) - nouveaux_t} mis à jour")
        print(f"Feeders reconnus : {sum(1 for n in noeuds if n['feeder_id'])} postes sur {len(noeuds)} ;"
              f" {len(non_resolus)} noms de départ inconnus de SIRV2")

        rapport = get_settings().reports_dir / f"sig_arcgis_{datetime.now():%Y%m%d_%H%M}.csv"
        rapport.parent.mkdir(parents=True, exist_ok=True)
        with rapport.open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(["depart_arcgis_inconnu_de_sirv2", "objets"])
            w.writerows(non_resolus.most_common())
        print(f"Départs non reconnus : {rapport}")

        if not args.execute:
            print("Simulation : rien n'a été écrit. Relancez avec --execute après une sauvegarde de la base.")
            return 0

        maintenant = datetime.now()
        colonnes_n = ["nom", "nom_feeder", "feeder_id", "station", "poste_source", "coord_x", "coord_y", "delegation",
                      "region", "puissance", "famille_poste", "cellule", "statut_validation", "est_actif", "date_maj"]
        for n in noeuds:
            if n["global_id"] in existants_n:
                session.execute(text(
                    f"UPDATE dbo.noeuds_sig SET {', '.join(f'{c} = :{c}' for c in colonnes_n)} WHERE global_id = :global_id"), n)
            else:
                min_n -= 1
                session.execute(text(
                    f"INSERT INTO dbo.noeuds_sig (legacy_id, legacy_fid, source, global_id, {', '.join(colonnes_n)})"
                    f" VALUES (:lid, :lid, 'arcgis', :global_id, {', '.join(':' + c for c in colonnes_n)})"), {**n, "lid": min_n})
        if remplaces or retires:
            for lot in range(0, len(remplaces + retires), 500):
                ids = (remplaces + retires)[lot:lot + 500]
                session.execute(text(f"UPDATE dbo.noeuds_sig SET est_actif = 0 WHERE id IN ({', '.join(str(int(i)) for i in ids)})"))

        colonnes_t = ["nom_feeder", "feeder_id", "nom_troncon", "nom_noeud_amont", "nom_noeud_aval", "tension_kv",
                      "longueur_m", "section", "poste_source", "type_conducteur", "delegation", "date_maj"]
        for t in troncons:
            t["date_chargement"] = maintenant
            if t["global_id"] in existants_t:
                session.execute(text(
                    f"UPDATE dbo.troncons_sig SET {', '.join(f'{c} = :{c}' for c in colonnes_t)}, date_chargement = :date_chargement"
                    " WHERE global_id = :global_id"), t)
            else:
                min_t -= 1
                session.execute(text(
                    f"INSERT INTO dbo.troncons_sig (legacy_id, legacy_fid, source, global_id, date_chargement, {', '.join(colonnes_t)})"
                    # legacy_fid négatif aussi : unicité (legacy_fid, date_chargement) de uq_troncons_sig_fid_chargement
                    f" VALUES (:lid, :lid, 'arcgis', :global_id, :date_chargement, {', '.join(':' + c for c in colonnes_t)})"),
                    {**t, "lid": min_t})
        for requete in RECALCUL_DERNIER_CHARGEMENT:
            session.execute(text(requete))
    print("SIG mis à jour. Les écrans SIG se rafraîchissent au plus tard dans 6 h (cache), ou au redémarrage de Redis.")
    return 0


if __name__ == "__main__":
    from scripts.migration._bootstrap import terminer

    terminer(main())
