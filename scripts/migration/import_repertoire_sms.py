#!/usr/bin/env python3
"""Reprise du répertoire SMS de SIR v1 dans les destinataires SIRV2.

Source : HFSQL SIR v1
  - GroupeEnvoi (Groupe)                          → dbo.groupes_envoi
  - Destinataire (prénomnom, Telephone, Fonctiondes, Groupe) → dbo.destinataires
    (c'est la liste « Répertoire » de l'ancienne page SMS : Fonction, Agent, Téléphone, Groupe)
  - Repertoire (Prénom, Nom, fonctionagent, Telephone) : annuaire des agents, repris seulement
    avec --repertoire (agents sans groupe).

Règles :
  - un destinataire par numéro (9 chiffres, sans indicatif), membre de tous ses groupes
    (SIR v1 répète la personne sur une ligne par groupe) ;
  - les destinataires SIRV2 qui partagent un numéro (reprise ETL : une ligne par groupe) sont
    fusionnés : on garde le plus ancien, l'historique SMS/e-mail lui est rattaché ;
  - un numéro déjà présent dans SIRV2 est complété (groupes, fonction, matricule) sans changer
    son nom, son e-mail ni son service ;
  - chaque groupe garde son exploitation SIR v1 (BCC, BRC, DISPATCHING) ;
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
    groupes: set[str] = field(default_factory=set)
    matricule: int | None = None
    sources: set[str] = field(default_factory=set)


def _matricule(valeur: str) -> int | None:
    try:
        m = int(float(valeur))
    except (TypeError, ValueError):
        return None
    return m if m > 0 else None


EXPLOITATIONS = {"BCC", "BRC", "DISPATCHING"}


def _exploitation(valeur: str) -> str | None:
    v = valeur.strip().upper()
    return v if v in EXPLOITATIONS else None


def construire(
    groupes_v1: list[dict[str, Any]],
    destinataires_v1: list[dict[str, Any]],
    repertoire_v1: list[dict[str, Any]],
) -> tuple[dict[str, str | None], dict[str, Contact], Counter]:
    """Groupes (libellé → exploitation) et contacts dédoublonnés par numéro, avec les rejets."""
    rejets: Counter = Counter()
    groupes: dict[str, str | None] = {}
    for g in groupes_v1:
        libelle = champ(g, "Groupe")
        if libelle:
            groupes[libelle] = _exploitation(champ(g, "exploitation")) or groupes.get(libelle)
    contacts: dict[str, Contact] = {}

    for row in destinataires_v1:
        tel = normaliser_numero(champ(row, "Telephone"))
        if len(tel) < 7:
            rejets["destinataire sans numéro valide"] += 1
            continue
        groupe = champ(row, "Groupe")
        if groupe and groupe not in groupes:
            groupes[groupe] = _exploitation(champ(row, "exploitation"))
        existant = contacts.get(tel)
        if existant:
            rejets["ligne supplémentaire (même numéro, autre groupe)"] += 1
            if groupe:
                existant.groupes.add(groupe)
            existant.fonction = existant.fonction or champ(row, "Fonctiondes")[:100]
            existant.matricule = existant.matricule or _matricule(champ(row, "Matricule"))
            continue
        contacts[tel] = Contact(
            tel,
            (champ(row, "prénomnom", "prenomnom") or tel)[:200],
            champ(row, "Fonctiondes")[:100],
            {groupe} if groupe else set(),
            _matricule(champ(row, "Matricule")),
            {"Destinataire"},
        )

    for row in repertoire_v1:
        tel = normaliser_numero(champ(row, "Telephone"))
        if len(tel) < 7:
            rejets["agent sans numéro valide"] += 1
            continue
        existant = contacts.get(tel)
        if existant:
            existant.fonction = existant.fonction or champ(row, "fonctionagent")[:100]
            existant.matricule = existant.matricule or _matricule(champ(row, "Matricule"))
            existant.sources.add("Repertoire")
            continue
        nom = " ".join(p for p in (champ(row, "Prénom", "Prenom"), champ(row, "Nom")) if p) or tel
        contacts[tel] = Contact(
            tel, nom[:200], champ(row, "fonctionagent")[:100], set(), _matricule(champ(row, "Matricule")), {"Repertoire"}
        )

    return dict(sorted(groupes.items())), contacts, rejets


def lire_hfsql(avec_repertoire: bool) -> tuple[list[dict], list[dict], list[dict]]:
    conn = connect_hfsql()
    try:
        groupes = list(fetch_table(conn, "GroupeEnvoi"))
        destinataires = list(fetch_table(conn, "Destinataire"))
        repertoire = list(fetch_table(conn, "Repertoire")) if avec_repertoire else []
    finally:
        conn.close()
    return groupes, destinataires, repertoire


def _doublons_sirv2(session) -> dict[str, list[int]]:
    """Destinataires SIRV2 par numéro normalisé (plusieurs id = doublons à fusionner)."""
    par_numero: dict[str, list[int]] = {}
    for i, tel in session.execute(
        text("SELECT id, telephone FROM dbo.destinataires WHERE telephone IS NOT NULL ORDER BY id")
    ).all():
        cle = normaliser_numero(tel)
        if cle:
            par_numero.setdefault(cle, []).append(int(i))
    return par_numero


def fusionner(session, garder: int, autres: list[int]) -> None:
    """Rattache historique et groupes des doublons au destinataire gardé, puis supprime les doublons."""
    p = {"g": garder}
    for autre in autres:
        p["a"] = autre
        session.execute(text("UPDATE dbo.sms_envoyes SET destinataire_id = :g WHERE destinataire_id = :a"), p)
        session.execute(text("UPDATE dbo.emails_envoyes SET destinataire_id = :g WHERE destinataire_id = :a"), p)
        session.execute(
            text(
                "INSERT INTO dbo.destinataire_groupes (destinataire_id, groupe_id) "
                "SELECT :g, x.groupe_id FROM dbo.destinataire_groupes x WHERE x.destinataire_id = :a "
                "AND NOT EXISTS (SELECT 1 FROM dbo.destinataire_groupes y WHERE y.destinataire_id = :g "
                "AND y.groupe_id = x.groupe_id)"
            ),
            p,
        )
        session.execute(
            text(
                "UPDATE dbo.destinataires SET "
                "service_id = COALESCE(service_id, (SELECT x.service_id FROM dbo.destinataires x WHERE x.id = :a)), "
                "email = COALESCE(email, (SELECT x.email FROM dbo.destinataires x WHERE x.id = :a)), "
                "utilisateur_id = COALESCE(utilisateur_id, (SELECT x.utilisateur_id FROM dbo.destinataires x WHERE x.id = :a)), "
                "fonction = COALESCE(fonction, (SELECT x.fonction FROM dbo.destinataires x WHERE x.id = :a)), "
                "matricule = COALESCE(matricule, (SELECT x.matricule FROM dbo.destinataires x WHERE x.id = :a)) "
                "WHERE id = :g"
            ),
            p,
        )
        session.execute(text("DELETE FROM dbo.destinataire_groupes WHERE destinataire_id = :a"), p)
        session.execute(text("DELETE FROM dbo.destinataires WHERE id = :a"), p)


def ecrire(session, groupes: dict[str, str | None], contacts: dict[str, Contact]) -> dict[str, int]:
    bilan = Counter()
    ids_groupes: dict[str, int] = {}
    for i, lib, expl in session.execute(text("SELECT id, libelle, exploitation FROM dbo.groupes_envoi")).all():
        ids_groupes[lib] = int(i)
        if not expl and groupes.get(lib):
            session.execute(text("UPDATE dbo.groupes_envoi SET exploitation = :e WHERE id = :i"), {"e": groupes[lib], "i": i})
    for libelle, exploitation in groupes.items():
        if libelle in ids_groupes:
            continue
        session.execute(
            text("INSERT INTO dbo.groupes_envoi (libelle, is_active, exploitation) VALUES (:l, 1, :e)"),
            {"l": libelle[:255], "e": exploitation},
        )
        ids_groupes[libelle] = int(
            session.execute(text("SELECT id FROM dbo.groupes_envoi WHERE libelle = :l"), {"l": libelle[:255]}).scalar_one()
        )
        bilan["groupes_crees"] += 1

    existants: dict[str, int] = {}
    for numero, ids in _doublons_sirv2(session).items():
        existants[numero] = ids[0]
        if len(ids) > 1:
            fusionner(session, ids[0], ids[1:])
            bilan["doublons_fusionnes"] += len(ids) - 1

    liens = {
        (int(d), int(g)) for d, g in session.execute(text("SELECT destinataire_id, groupe_id FROM dbo.destinataire_groupes")).all()
    }
    for tel, c in contacts.items():
        ident = existants.get(tel)
        if ident is None:
            session.execute(
                text(
                    "INSERT INTO dbo.destinataires (nom, telephone, email, utilisateur_id, service_id, is_active, fonction, matricule) "
                    "VALUES (:nom, :tel, NULL, NULL, NULL, 1, :fonction, :matricule)"
                ),
                {"nom": c.nom, "tel": tel, "fonction": c.fonction or None, "matricule": c.matricule},
            )
            ident = int(
                session.execute(text("SELECT MAX(id) FROM dbo.destinataires WHERE telephone = :t"), {"t": tel}).scalar_one()
            )
            bilan["destinataires_crees"] += 1
        else:
            session.execute(
                text(
                    "UPDATE dbo.destinataires SET fonction = COALESCE(fonction, :fonction), "
                    "matricule = COALESCE(matricule, :matricule) WHERE id = :id"
                ),
                {"fonction": c.fonction or None, "matricule": c.matricule, "id": ident},
            )
            bilan["destinataires_completes"] += 1
        for groupe in c.groupes:
            gid = ids_groupes[groupe]
            if (ident, gid) not in liens:
                session.execute(
                    text("INSERT INTO dbo.destinataire_groupes (destinataire_id, groupe_id) VALUES (:d, :g)"),
                    {"d": ident, "g": gid},
                )
                liens.add((ident, gid))
                bilan["appartenances_ajoutees"] += 1
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
    par_groupe: Counter = Counter()
    for c in contacts.values():
        for g in c.groupes or {"(sans groupe)"}:
            par_groupe[g] += 1
    multi = sum(1 for c in contacts.values() if len(c.groupes) > 1)
    print(f"\n{len(contacts)} numéro(s) distinct(s), {len(groupes)} groupe(s), {multi} personne(s) dans plusieurs groupes :")
    for groupe, n in sorted(par_groupe.items()):
        print(f"  {groupe:<40} {groupes.get(groupe) or '':<12} {n:>5}")
    if rejets:
        print(f"Écartés : {dict(rejets)}")

    bilan: dict[str, Any] = {"simulation": not args.execute, "numeros": len(contacts), "groupes": len(groupes)}
    with get_session() as session:
        if args.execute:
            bilan.update(ecrire(session, groupes, contacts))
        else:
            deja = _doublons_sirv2(session)
            bilan["deja_dans_sirv2"] = sum(1 for t in contacts if t in deja)
            bilan["a_creer"] = len(contacts) - bilan["deja_dans_sirv2"]
            bilan["doublons_sirv2_a_fusionner"] = sum(len(ids) - 1 for ids in deja.values())
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
