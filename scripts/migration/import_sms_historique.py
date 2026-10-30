#!/usr/bin/env python3
"""Reprise de l'historique des SMS envoyés par SIR v1 (table smsenvoye) dans dbo.sms_envoyes.

SIR v1 : smsenvoye (NInterruption, dateEnvoi, exploitation, Login, messageenvoye, Telephone,
destinataire, Status_Code, Status_Text, messageID).

Correspondances :
  - destinataire  : destinataire SIRV2 de même numéro (9 chiffres) ; s'il n'existe pas, une fiche
                    INACTIVE est créée (nom SIR v1 ou numéro) pour garder la trace sans recevoir de SMS ;
  - interruption  : NInterruption → interruption SIRV2 de même numéro (entity_type « interruption ») ;
                    0 ou absent → envoi manuel (entity_type « manual ») ;
  - expéditeur    : Login SIR v1 (matricule) → login HFSQL (Utilisateurs) → utilisateur SIRV2 ;
  - statut        : Status_Code 200 → envoye ; sinon echec, motif = Status_Text (« PAS DE REPONSE »…).

Relancer le script ne crée pas de doublon : un SMS déjà repris (même date, même numéro, même
message) est ignoré. Simulation par défaut ; tester sur une copie de la base avant --execute.

Usage (poste ETL avec le pilote ODBC HFSQL, réseau SENELEC) :
    python scripts/migration/import_sms_historique.py                  # simulation
    python scripts/migration/import_sms_historique.py --depuis 2024    # à partir de 2024
    python scripts/migration/import_sms_historique.py --execute
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime
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
from scripts.migration.import_repertoire_sms import champ, normaliser_numero  # noqa: E402

LOT = 500


def _date(valeur: str) -> datetime | None:
    if not valeur:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%d"):
        try:
            return datetime.strptime(valeur[:26], fmt)
        except ValueError:
            continue
    return None


def _entier(valeur: str) -> int:
    try:
        return int(float(valeur))
    except (TypeError, ValueError):
        return 0


def preparer(rows: list[dict[str, Any]], depuis: int) -> tuple[list[dict[str, Any]], Counter]:
    """Lignes smsenvoye normalisées (date, numéro, message, statut…) et décompte des rejets."""
    sms: list[dict[str, Any]] = []
    rejets: Counter = Counter()
    for row in rows:
        quand = _date(champ(row, "dateEnvoi"))
        if quand is None:
            rejets["sans date d'envoi"] += 1
            continue
        if quand.year < depuis:
            continue
        numero = normaliser_numero(champ(row, "Telephone"))
        if len(numero) < 7:
            rejets["sans numéro valide"] += 1
            continue
        code = champ(row, "Status_Code")
        texte = champ(row, "Status_Text")
        sms.append(
            {
                "date": quand,
                "numero": numero,
                "nom": champ(row, "destinataire") or numero,
                "contenu": (champ(row, "messageenvoye") or "(message vide)")[:1000],
                "interruption": _entier(champ(row, "NInterruption")),
                "login": champ(row, "Login"),
                "statut": "envoye" if code == "200" else "echec",
                "code": code[:20] or None,
                "erreur": None if code == "200" else (texte or "PAS DE REPONSE")[:500],
                "message_id": champ(row, "messageID")[:50] or None,
            }
        )
    return sms, rejets


def _cle_date(valeur: Any) -> str:
    """Date à la seconde, quel que soit le type renvoyé par le pilote (datetime ou texte)."""
    return str(valeur)[:19].replace("T", " ") if valeur else ""


def ecrire(session, sms: list[dict[str, Any]], logins_v1: dict[str, str]) -> dict[str, int]:
    bilan: Counter = Counter()
    destinataires: dict[str, int] = {}
    for i, tel in session.execute(
        text("SELECT id, telephone FROM dbo.destinataires WHERE telephone IS NOT NULL ORDER BY id")
    ).all():
        destinataires.setdefault(normaliser_numero(tel), int(i))
    interruptions = {
        int(n): int(i)
        for n, i in session.execute(
            text("SELECT numero_interruption, MIN(id) FROM dbo.interruptions GROUP BY numero_interruption")
        ).all()
    }
    utilisateurs = {str(lg).lower(): int(i) for i, lg in session.execute(text("SELECT id, login FROM dbo.utilisateurs")).all()}
    deja = {
        (_cle_date(d), normaliser_numero(t or ""), (c or "")[:60])
        for d, t, c in session.execute(
            text(
                "SELECT s.sent_at, d.telephone, s.contenu FROM dbo.sms_envoyes s "
                "JOIN dbo.destinataires d ON d.id = s.destinataire_id WHERE s.sent_at IS NOT NULL"
            )
        ).all()
    }

    lot: list[dict[str, Any]] = []
    for s in sms:
        cle = (_cle_date(s["date"]), s["numero"], s["contenu"][:60])
        if cle in deja:
            bilan["deja_repris"] += 1
            continue
        deja.add(cle)
        dest_id = destinataires.get(s["numero"])
        if dest_id is None:
            session.execute(
                text(
                    "INSERT INTO dbo.destinataires (nom, telephone, email, utilisateur_id, service_id, is_active) "
                    "VALUES (:nom, :tel, NULL, NULL, NULL, 0)"
                ),
                {"nom": s["nom"][:200], "tel": s["numero"]},
            )
            dest_id = int(
                session.execute(text("SELECT MAX(id) FROM dbo.destinataires WHERE telephone = :t"), {"t": s["numero"]}).scalar_one()
            )
            destinataires[s["numero"]] = dest_id
            bilan["destinataires_inactifs_crees"] += 1
        interruption_id = interruptions.get(s["interruption"]) if s["interruption"] else None
        if s["interruption"] and interruption_id is None:
            bilan["interruption_introuvable"] += 1
        login = logins_v1.get(s["login"], s["login"]).lower()
        lot.append(
            {
                "dest": dest_id,
                "etype": "interruption" if interruption_id else "manual",
                "eid": interruption_id,
                "contenu": s["contenu"],
                "statut": s["statut"],
                "sent_at": s["date"],
                "erreur": s["erreur"],
                "created_at": s["date"],
                "par": utilisateurs.get(login),
                "code": s["code"],
                "mid": s["message_id"],
            }
        )
        bilan[f"sms_{s['statut']}"] += 1
        if len(lot) >= LOT:
            _inserer(session, lot)
            lot = []
    if lot:
        _inserer(session, lot)
    return dict(bilan)


def _inserer(session, lot: list[dict[str, Any]]) -> None:
    session.execute(
        text(
            "INSERT INTO dbo.sms_envoyes (destinataire_id, entity_type, entity_id, contenu, statut, sent_at, erreur, "
            "created_at, envoye_par_id, code_retour, message_id) VALUES (:dest, :etype, :eid, :contenu, :statut, "
            ":sent_at, :erreur, :created_at, :par, :code, :mid)"
        ),
        lot,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--execute", action="store_true", help="Écrire en base (sinon simulation)")
    parser.add_argument("--depuis", type=int, default=2000, help="Première année reprise")
    args = parser.parse_args()
    ensure_dirs()
    settings = get_settings()
    print(f"Source : {settings.hfsql_server} / {settings.hfsql_database} — table smsenvoye")

    conn = connect_hfsql()
    try:
        rows = list(fetch_table(conn, "smsenvoye"))
        logins_v1 = {
            champ(u, "Matricule"): champ(u, "Login")
            for u in fetch_table(conn, "Utilisateurs")
            if champ(u, "Matricule") and champ(u, "Login")
        }
    finally:
        conn.close()
    sms, rejets = preparer(rows, args.depuis)
    par_annee = Counter(s["date"].year for s in sms)
    print(f"{len(rows)} ligne(s) lue(s), {len(sms)} retenue(s)")
    for annee, n in sorted(par_annee.items()):
        envoyes = sum(1 for s in sms if s["date"].year == annee and s["statut"] == "envoye")
        print(f"  {annee} : {n:>7} SMS dont {envoyes:>7} envoyés")
    if rejets:
        print(f"Écartés : {dict(rejets)}")

    bilan: dict[str, Any] = {"simulation": not args.execute, "lus": len(rows), "retenus": len(sms)}
    with get_session() as session:
        bilan.update(ecrire(session, sms, logins_v1))
        if not args.execute:
            session.rollback()
    print("\n" + json.dumps(bilan, ensure_ascii=False))
    rapport = settings.reports_dir / "import_sms_historique.json"
    rapport.write_text(json.dumps({**bilan, "rejets": dict(rejets)}, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Rapport : {rapport}")
    if not args.execute:
        print("\nSimulation : rien n'a été écrit (les chiffres ci-dessus sont ceux d'une reprise). Relancer avec --execute.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
