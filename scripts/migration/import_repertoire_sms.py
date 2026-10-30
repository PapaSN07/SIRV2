#!/usr/bin/env python3
"""Reprise du répertoire SMS de SIR v1 dans les destinataires SIRV2.

Source : HFSQL SIR v1
  - GroupeEnvoi (Groupe)                          → dbo.groupes_envoi
  - Destinataire (prénomnom, Telephone, Fonctiondes, Groupe) → dbo.destinataires
    (c'est la liste « Répertoire » de l'ancienne page SMS : Fonction, Agent, Téléphone, Groupe)
  - Repertoire (Prénom, Nom, fonctionagent, Telephone) : annuaire des agents, repris seulement
    avec --repertoire (agents sans groupe).

Règles :
  - un destinataire par numéro (9 chiffres, sans indicatif) ; un numéro déjà présent dans SIRV2
    est complété (groupe, fonction) sans changer son nom, son e-mail ni son service ;
  - les nouveaux destinataires sont créés SANS service : ils servent aux envois manuels de la
    page SMS et ne reçoivent pas les SMS automatiques des interruptions (qui vont aux
    destinataires rattachés au service de l'interruption).

La simulation (par défaut) n'écrit rien. Tester sur une copie de la base avant --execute.

Usage (poste ETL avec le pilote ODBC HFSQL, réseau SENELEC) :
    python scripts/migration/import_repertoire_sms.py                 # simulation
    python scripts/migration/import_repertoire_sms.py --repertoire    # + annuaire des agents
    python scripts/migration/import_repertoire_sms.py --execute       # écriture
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import scripts.migration._bootstrap  # noqa: F401,E402
from sqlalchemy import text  # noqa: E402

from scripts.migration.config import ensure_dirs, get_settings  # noqa: E402
from scripts.migration.db_session import get_session  # noqa: E402
from scripts.migration.hfsql_odbc import connect_hfsql, fetch_table  # noqa: E402


def _cle(nom: str) -> str:
    sans_accent = unicodedata.normalize("NFKD", str(nom)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z]", "", sans_accent.lower())


def champ(row: dict[str, Any], *noms: str) -> str:
    """Valeur texte d'une colonne, quels que soient accents et casse du nom renvoyé par l'ODBC."""
    index = {_cle(k): v for k, v in row.items()}
    for nom in noms:
        v = index.get(_cle(nom))
        if v is not None and str(v).strip():
            return " ".join(str(v).split())
    return ""


def normaliser_numero(numero: str) -> str:
    """Même règle que l'envoi (app/services/sms_gateway.py) : 9 chiffres sans indicatif."""
    chiffres = re.sub(r"\D", "", numero or "")
    if chiffres.startswith("00221"):
        chiffres = chiffres[5:]
    elif chiffres.startswith("221") and len(chiffres) == 12:
        chiffres = chiffres[3:]
    return chiffres


@dataclass
class Contact:
    telephone: str
    nom: str
    fonction: str = ""
    groupe: str = ""
    sources: set[str] = field(default_factory=set)


def construire(
    groupes_v1: list[dict[str, Any]],
    destinataires_v1: list[dict[str, Any]],
    repertoire_v1: list[dict[str, Any]],
) -> tuple[list[str], dict[str, Contact], Counter]:
    """Groupes et contacts dédoublonnés par numéro, avec le décompte des lignes écartées."""
    rejets: Counter = Counter()
    groupes = sorted({champ(g, "Groupe") for g in groupes_v1} - {""})
    contacts: dict[str, Contact] = {}

    for row in destinataires_v1:
        tel = normaliser_numero(champ(row, "Telephone"))
        if len(tel) < 7:
            rejets["destinataire sans numéro valide"] += 1
            continue
        nom = champ(row, "prénomnom", "prenomnom") or tel
        groupe = champ(row, "Groupe")
        if groupe and groupe not in groupes:
            groupes.append(groupe)
        existant = contacts.get(tel)
        if existant:
            rejets["destinataire en double (même numéro)"] += 1
            existant.groupe = existant.groupe or groupe
            existant.fonction = existant.fonction or champ(row, "Fonctiondes")
            continue
        contacts[tel] = Contact(tel, nom[:200], champ(row, "Fonctiondes")[:100], groupe, {"Destinataire"})

    for row in repertoire_v1:
        tel = normaliser_numero(champ(row, "Telephone"))
        if len(tel) < 7:
            rejets["agent sans numéro valide"] += 1
            continue
        nom = " ".join(p for p in (champ(row, "Prénom", "Prenom"), champ(row, "Nom")) if p) or tel
        existant = contacts.get(tel)
        if existant:
            existant.fonction = existant.fonction or champ(row, "fonctionagent")[:100]
            existant.sources.add("Repertoire")
            continue
        contacts[tel] = Contact(tel, nom[:200], champ(row, "fonctionagent")[:100], "", {"Repertoire"})

    return sorted(groupes), contacts, rejets


def lire_hfsql(avec_repertoire: bool) -> tuple[list[dict], list[dict], list[dict]]:
    conn = connect_hfsql()
    try:
        groupes = list(fetch_table(conn, "GroupeEnvoi"))
        destinataires = list(fetch_table(conn, "Destinataire"))
        repertoire = list(fetch_table(conn, "Repertoire")) if avec_repertoire else []
    finally:
        conn.close()
    return groupes, destinataires, repertoire


def ecrire(session, groupes: list[str], contacts: dict[str, Contact]) -> dict[str, int]:
    bilan = Counter()
    ids_groupes = {lib: int(i) for i, lib in session.execute(text("SELECT id, libelle FROM dbo.groupes_envoi")).all()}
    for libelle in groupes:
        if libelle not in ids_groupes:
            session.execute(
                text("INSERT INTO dbo.groupes_envoi (libelle, is_active) VALUES (:l, 1)"), {"l": libelle[:255]}
            )
            ids_groupes[libelle] = int(
                session.execute(text("SELECT id FROM dbo.groupes_envoi WHERE libelle = :l"), {"l": libelle[:255]}).scalar_one()
            )
            bilan["groupes_crees"] += 1

    existants: dict[str, tuple[int, int | None, str | None]] = {}
    for i, tel, groupe_id, fonction in session.execute(
        text("SELECT id, telephone, groupe_id, fonction FROM dbo.destinataires WHERE telephone IS NOT NULL")
    ).all():
        cle = normaliser_numero(tel)
        if cle and cle not in existants:
            existants[cle] = (int(i), groupe_id, fonction)

    for tel, c in contacts.items():
        groupe_id = ids_groupes.get(c.groupe) if c.groupe else None
        if tel in existants:
            ident, groupe_actuel, fonction_actuelle = existants[tel]
            maj = {}
            if groupe_id and not groupe_actuel:
                maj["groupe_id"] = groupe_id
            if c.fonction and not fonction_actuelle:
                maj["fonction"] = c.fonction
            if maj:
                sets = ", ".join(f"{k} = :{k}" for k in maj)
                session.execute(text(f"UPDATE dbo.destinataires SET {sets} WHERE id = :id"), {**maj, "id": ident})
                bilan["destinataires_completes"] += 1
            else:
                bilan["destinataires_inchanges"] += 1
            continue
        session.execute(
            text(
                "INSERT INTO dbo.destinataires (nom, telephone, email, utilisateur_id, service_id, is_active, fonction, groupe_id) "
                "VALUES (:nom, :tel, NULL, NULL, NULL, 1, :fonction, :groupe_id)"
            ),
            {"nom": c.nom, "tel": tel, "fonction": c.fonction or None, "groupe_id": groupe_id},
        )
        bilan["destinataires_crees"] += 1
    return dict(bilan)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--execute", action="store_true", help="Écrire en base (sinon simulation)")
    parser.add_argument("--repertoire", action="store_true", help="Ajouter aussi l'annuaire des agents (table Repertoire)")
    args = parser.parse_args()
    ensure_dirs()
    settings = get_settings()
    print(f"Source : {settings.hfsql_server} / {settings.hfsql_database}")

    groupes_v1, destinataires_v1, repertoire_v1 = lire_hfsql(args.repertoire)
    print(
        f"Lu : {len(groupes_v1)} groupe(s), {len(destinataires_v1)} destinataire(s)"
        + (f", {len(repertoire_v1)} agent(s) du répertoire" if args.repertoire else "")
    )
    groupes, contacts, rejets = construire(groupes_v1, destinataires_v1, repertoire_v1)
    par_groupe = Counter(c.groupe or "(sans groupe)" for c in contacts.values())
    print(f"\n{len(contacts)} numéro(s) distinct(s), {len(groupes)} groupe(s) :")
    for groupe, n in sorted(par_groupe.items()):
        print(f"  {groupe:<40} {n:>5}")
    if rejets:
        print(f"Écartés : {dict(rejets)}")

    bilan: dict[str, Any] = {"simulation": not args.execute, "numeros": len(contacts), "groupes": len(groupes)}
    with get_session() as session:
        if args.execute:
            bilan.update(ecrire(session, groupes, contacts))
        else:
            deja = {
                normaliser_numero(t)
                for (t,) in session.execute(text("SELECT telephone FROM dbo.destinataires WHERE telephone IS NOT NULL")).all()
            }
            bilan["deja_dans_sirv2"] = sum(1 for t in contacts if t in deja)
            bilan["a_creer"] = len(contacts) - bilan["deja_dans_sirv2"]
            session.rollback()
    print("\n" + json.dumps(bilan, ensure_ascii=False))
    rapport = settings.reports_dir / "import_repertoire_sms.json"
    rapport.write_text(
        json.dumps({**bilan, "rejets": dict(rejets), "par_groupe": dict(par_groupe)}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"Rapport : {rapport}")
    if not args.execute:
        print("\nSimulation : rien n'a été écrit. Relancer avec --execute pour importer.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
