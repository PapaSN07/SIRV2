#!/usr/bin/env python3
"""Backfill workflows (une ligne par étape) depuis HFSQL Interruptions (exports ou live)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import scripts.migration._bootstrap  # noqa: F401
from scripts.migration.config import get_settings
from scripts.migration.hfsql_odbc import iter_table_rows
from scripts.migration.id_maps import IdMapStore
from scripts.migration.transforms.dates import merge_date_time, parse_datetime
from scripts.migration.transforms.rows import row_get
from sqlalchemy import create_engine, text

WORKFLOW_DATE_FIELDS: tuple[tuple[str, str, str], ...] = (
    ("date_debut_declenchement", "DateDebutDeclenchement", "HeuredebutDeclenchement"),
    ("date_fin_declenchement", "DateFinDeclenchement", "HeureFinDeclanchem"),
    ("date_interpellation_pdm", "DateInterpellationPDM", "HeureInterpellationPDM"),
    ("date_arrivee_pdm", "DateArriveePDM", "HeureArriveePDM"),
    ("date_debut_tronconnement", "DebutTronconn", "heuredebutTronco"),
    ("date_fin_tronconnement", "DateFInTronconnement", "HeureFinTronc"),
    ("date_debut_localisation", "DateDebutLocal", "heuredeLocalisation"),
    ("date_fin_localisation", "FinLocal", "HeureFinLocal"),
    ("date_debut_reparation", "DebutRepartion", "HeureDebutReparation"),
    ("date_fin_reparation", "DareFinRepartion", "HeureFinreparation"),
    ("date_debut_remise", "DebutRemise", "HeureDebutRemise"),
    ("date_fin_remise", "DateFinRemise", "HeureFinRemise"),
)


_SQL_DATETIME_MIN_YEAR = 1753  # colonnes DATETIME SQL Server (migration workflow)


def _valid_sql_datetime(dt) -> Any:
    """Rejette les sentinelles HFSQL (ex. année 1000) hors plage DATETIME."""
    if dt is None:
        return None
    if dt.year < _SQL_DATETIME_MIN_YEAR or dt.year > 9999:
        return None
    return dt


def _parse_dt(row: dict[str, Any], date_key: str, time_key: str | None = None):
    date_val = row_get(row, date_key, date_key.lower())
    if time_key:
        time_val = row_get(row, time_key, time_key.lower())
        merged = merge_date_time(date_val, time_val)
        if merged:
            return _valid_sql_datetime(merged)
    return _valid_sql_datetime(parse_datetime(date_val))


def _resolve_troncon_sig_id(id_maps: IdMapStore, legacy_sig: Any) -> int | None:
    try:
        lid = int(legacy_sig)
    except (TypeError, ValueError):
        return None
    if lid <= 0:
        return None
    mapped = id_maps.get("troncons_sig", lid)
    return int(mapped) if mapped is not None else None


def _split_nomtroncon(nom: str) -> tuple[str | None, str | None]:
    text = nom.strip()
    if not text:
        return None, None
    if " - " in text:
        amont, aval = text.split(" - ", 1)
        return amont.strip() or None, aval.strip() or None
    return text, None


def _workflow_row_from_hfsql(row: dict[str, Any], id_maps: IdMapStore) -> dict[str, Any] | None:
    legacy_id = row_get(row, "NInterruption", "ninterruption")
    if legacy_id is None:
        return None
    sir_id = id_maps.get("interruptions", legacy_id)
    if sir_id is None:
        return None

    values: dict[str, Any] = {"interruption_id": int(sir_id)}
    has_data = False

    for col, date_key, time_key in WORKFLOW_DATE_FIELDS:
        dt = _parse_dt(row, date_key, time_key)
        if dt is not None:
            values[col] = dt
            has_data = True

    legacy_troncon = row_get(row, "IDTroncon", "idtroncon")
    if legacy_troncon is not None:
        troncon_id = id_maps.get("troncons", legacy_troncon)
        if troncon_id is not None:
            values["troncon_id"] = int(troncon_id)
            has_data = True

    troncon_sig = row_get(row, "IDTronconSIG", "ID_Troncon_SIG", "idtronconsig")
    if troncon_sig is not None:
        sir_sig_id = _resolve_troncon_sig_id(id_maps, troncon_sig)
        if sir_sig_id is not None:
            values["troncon_sig_id"] = sir_sig_id
            has_data = True

    for col, key in (
        ("noeud_amont_libelle", "NoeudAmont"),
        ("noeud_aval_libelle", "NoeudAval"),
    ):
        val = row_get(row, key, key.lower())
        if val:
            values[col] = str(val)[:255]
            has_data = True

    nom_troncon = row_get(row, "NomTroncon", "nomtroncon")
    if nom_troncon and str(nom_troncon).strip():
        amont, aval = _split_nomtroncon(str(nom_troncon))
        if amont and "noeud_amont_libelle" not in values:
            values["noeud_amont_libelle"] = amont[:255]
            has_data = True
        if aval and "noeud_aval_libelle" not in values:
            values["noeud_aval_libelle"] = aval[:255]
            has_data = True

    matricule = row_get(row, "Matricule", "matricule")
    if matricule is not None:
        try:
            m = int(matricule)
            if m > 0:
                values["responsable_matricule"] = m
                has_data = True
        except (TypeError, ValueError):
            pass

    if not has_data:
        return None
    return values


def collect_workflow_rows(id_maps: IdMapStore) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    seen: set[int] = set()
    skipped_sig = 0
    for row in iter_table_rows("Interruptions", allow_live=True):
        mapped = _workflow_row_from_hfsql(row, id_maps)
        if mapped is None:
            legacy_sig = row_get(row, "IDTronconSIG", "ID_Troncon_SIG", "idtronconsig")
            if legacy_sig is not None and _resolve_troncon_sig_id(id_maps, legacy_sig) is None:
                try:
                    if int(legacy_sig) > 0:
                        skipped_sig += 1
                except (TypeError, ValueError):
                    pass
            continue
        iid = mapped["interruption_id"]
        if iid in seen:
            continue
        seen.add(iid)
        rows.append(mapped)
    return {"rows": rows, "skipped_sig_unmapped": skipped_sig}


# (code étape, colonne début, colonne fin) — ids résolus depuis dbo.etapes_workflow
ETAPE_DATE_COLUMNS: tuple[tuple[str, str, str], ...] = (
    ("declenchement", "date_debut_declenchement", "date_fin_declenchement"),
    ("interpellation_pdm", "date_interpellation_pdm", "date_arrivee_pdm"),
    ("tronconnement", "date_debut_tronconnement", "date_fin_tronconnement"),
    ("localisation", "date_debut_localisation", "date_fin_localisation"),
    ("reparation", "date_debut_reparation", "date_fin_reparation"),
    ("remise", "date_debut_remise", "date_fin_remise"),
)
TRONCONNEMENT_EXTRA = ("troncon_id", "troncon_sig_id", "noeud_amont_libelle", "noeud_aval_libelle")


def explode_to_etapes(row: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    """Convertit une ligne plate HFSQL en lignes `workflows` (une par étape renseignée)."""
    out: list[tuple[str, dict[str, Any]]] = []
    for code, col_debut, col_fin in ETAPE_DATE_COLUMNS:
        debut, fin = row.get(col_debut), row.get(col_fin)
        if debut is not None and fin is not None and fin < debut:
            fin = None
        payload: dict[str, Any] = {}
        if debut is not None:
            payload["date_debut"] = debut
        if fin is not None:
            payload["date_fin"] = fin
        if code == "tronconnement":
            payload.update({k: row[k] for k in TRONCONNEMENT_EXTRA if row.get(k) is not None})
        if payload:
            out.append((code, payload))

    if row.get("responsable_matricule") is not None:
        if not out:
            out.append(("declenchement", {}))
        out[-1][1]["responsable_matricule"] = row["responsable_matricule"]
    return out


def apply_workflow_rows(rows: list[dict[str, Any]], *, dry_run: bool) -> dict[str, int]:
    from app.core.config import settings as app_settings

    if dry_run:
        return {"would_upsert": sum(len(explode_to_etapes(r)) for r in rows)}

    url = app_settings.database_url.replace("aioodbc", "pyodbc")
    engine = create_engine(url)
    inserted = 0
    updated = 0
    batch_size = 500

    with engine.connect() as conn:
        etape_ids = {
            code: eid
            for eid, code in conn.execute(text("SELECT id, code FROM dbo.etapes_workflow")).all()
        }
        for idx, row in enumerate(rows, start=1):
            interruption_id = row["interruption_id"]
            for code, payload in explode_to_etapes(row):
                etape_id = etape_ids[code]
                existing = conn.execute(
                    text(
                        "SELECT id FROM dbo.workflows "
                        "WHERE interruption_id = :iid AND etape_workflow_id = :eid"
                    ),
                    {"iid": interruption_id, "eid": etape_id},
                ).scalar_one_or_none()
                params = {"interruption_id": interruption_id, "etape_workflow_id": etape_id, **payload}
                if existing is None:
                    colnames = ", ".join(params.keys())
                    placeholders = ", ".join(f":{k}" for k in params)
                    conn.execute(
                        text(f"INSERT INTO dbo.workflows ({colnames}) VALUES ({placeholders})"),
                        params,
                    )
                    inserted += 1
                elif payload:
                    set_clause = ", ".join(f"{k} = :{k}" for k in payload)
                    conn.execute(
                        text(
                            f"UPDATE dbo.workflows SET {set_clause} "
                            "WHERE interruption_id = :interruption_id "
                            "AND etape_workflow_id = :etape_workflow_id"
                        ),
                        params,
                    )
                    updated += 1

            if idx % batch_size == 0:
                conn.commit()
                print(f"  … {idx}/{len(rows)} interruptions traitées", flush=True)
        conn.commit()

    return {"inserted": inserted, "updated": updated}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Collecte sans écriture SQL")
    args = parser.parse_args()

    settings = get_settings()
    id_maps = IdMapStore(settings.id_maps_dir)
    id_maps.load("troncons_sig")
    collected = collect_workflow_rows(id_maps)
    rows = collected["rows"]
    stats = apply_workflow_rows(rows, dry_run=args.dry_run)
    print(
        json.dumps(
            {
                "collected": len(rows),
                "skipped_sig_unmapped": collected["skipped_sig_unmapped"],
                **stats,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
