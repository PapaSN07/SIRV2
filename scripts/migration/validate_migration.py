#!/usr/bin/env python3
"""Validation post-migration — counts, END/SAIFI/SAIDI, FK orphelines."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import yaml

import scripts.migration._bootstrap  # noqa: F401
from scripts.migration.config import ensure_dirs, get_settings
from scripts.migration.hfsql_odbc import iter_jsonl, test_connection
from sqlalchemy import text

from scripts.migration.db_session import get_session

# Hors périmètre FK volontaire — données HFSQL orphelines / transport mal typé.
IGNORED_INTERRUPTION_IDS: frozenset[int] = frozenset({189})
IGNORED_INTERRUPTION_NOTES: dict[int, str] = {
    189: "NInterruption HFSQL 66277 — région TRANSPORT, idfeeder=628 absent de Feeders",
}


def _ignored_interruptions_sql() -> str:
    if not IGNORED_INTERRUPTION_IDS:
        return ""
    ids = ",".join(str(i) for i in sorted(IGNORED_INTERRUPTION_IDS))
    return f" AND id NOT IN ({ids})"


FK_CHECKS = [
    ("interruptions", "service_id", "services", "id"),
    ("interruptions", "feeder_id", "feeders", "id"),
    ("interruptions", "cause_id", "causes", "id"),
    ("interruptions", "created_by_id", "utilisateurs", "id"),
    ("feeders", "poste_source_id", "postes_sources", "id"),
    ("services", "agence_id", "agences", "id"),
    ("agences", "delegation_id", "delegations", "id"),
    ("delegations", "region_id", "regions", "id"),
    ("user_roles", "utilisateur_id", "utilisateurs", "id"),
    ("user_roles", "role_id", "roles", "id"),
    ("energie_nd", "interruption_id", "interruptions", "id"),
    ("poste_interruptions", "interruption_id", "interruptions", "id"),
    ("poste_interruptions", "poste_id", "postes", "id"),
    ("poste_interruptions", "feeder_id", "feeders", "id"),
    ("poste_interruptions", "service_id", "services", "id"),
    ("poste_interruptions", "poste_source_id", "postes_sources", "id"),
]

FEEDER_POSTE_SOURCE_INCONNU_CODE = "INCONNU"

COUNT_TABLES = [
    "regions",
    "delegations",
    "agences",
    "services",
    "causes",
    "feeders",
    "postes",
    "utilisateurs",
    "interruptions",
    "energie_nd",
    "saifi_saidi",
    "napt",
]


def _source_counts(exports_dir: Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    for path in exports_dir.glob("*.jsonl"):
        counts[path.stem] = sum(1 for _ in iter_jsonl(path))
    return counts


def _target_counts(session) -> dict[str, int]:
    counts: dict[str, int] = {}
    for table in COUNT_TABLES:
        row = session.execute(text(f"SELECT COUNT(*) FROM dbo.[{table}]")).scalar()
        counts[table] = int(row or 0)
    return counts


def _fk_orphans(session) -> dict[str, int]:
    orphans: dict[str, int] = {}
    for child, fk_col, parent, pk_col in FK_CHECKS:
        sql = text(
            f"""
            SELECT COUNT(*) FROM dbo.[{child}] c
            LEFT JOIN dbo.[{parent}] p ON c.[{fk_col}] = p.[{pk_col}]
            WHERE c.[{fk_col}] IS NOT NULL AND p.[{pk_col}] IS NULL
            """
        )
        orphans[f"{child}.{fk_col}"] = int(session.execute(sql).scalar() or 0)
    return orphans


def _end_totals(session) -> dict[str, float]:
    end_hfsql = 0.0
    exports = get_settings().exports_dir
    for path in (exports / "EnergieND.jsonl", exports / "Interruptions.jsonl"):
        if path.exists():
            for row in iter_jsonl(path):
                end_hfsql += float(row.get("ENDD") or 0)
    end_target = float(
        session.execute(text("SELECT COALESCE(SUM(valeur_mwh), 0) FROM dbo.energie_nd")).scalar() or 0
    )
    tolerance = 0.001
    delta_pct = abs(end_target - end_hfsql) / end_hfsql * 100 if end_hfsql else 0
    return {
        "source_end_mwh": round(end_hfsql, 4),
        "target_end_mwh": round(end_target, 4),
        "delta_pct": round(delta_pct, 4),
        "within_tolerance": delta_pct <= 0.1 or end_hfsql == 0,
    }


def _saifi_saidi_check(session) -> dict[str, Any]:
    source_total = 0.0
    path = get_settings().exports_dir / "SAIFISAIDI.jsonl"
    if path.exists():
        for row in iter_jsonl(path):
            source_total += float(row.get("SAIFI") or 0) + float(row.get("SAIDI") or 0)
    target_total = float(
        session.execute(
            text("SELECT COALESCE(SUM(saifi + saidi), 0) FROM dbo.saifi_saidi")
        ).scalar()
        or 0
    )
    delta_pct = abs(target_total - source_total) / source_total * 100 if source_total else 0
    return {
        "source_saifi_saidi_sum": round(source_total, 4),
        "target_saifi_saidi_sum": round(target_total, 4),
        "delta_pct": round(delta_pct, 4),
        "within_tolerance": delta_pct <= 0.1 or source_total == 0,
    }


def _feeder_poste_source_check(session) -> dict[str, Any]:
    """Chaque feeder doit être rattaché à un poste source réel (pas INCONNU)."""
    null_ps = int(
        session.execute(
            text("SELECT COUNT(*) FROM dbo.feeders WHERE poste_source_id IS NULL")
        ).scalar()
        or 0
    )
    inconnu = int(
        session.execute(
            text(
                """
                SELECT COUNT(*) FROM dbo.feeders f
                INNER JOIN dbo.postes_sources ps ON ps.id = f.poste_source_id
                WHERE ps.code = :code
                """
            ),
            {"code": FEEDER_POSTE_SOURCE_INCONNU_CODE},
        ).scalar()
        or 0
    )
    total = int(session.execute(text("SELECT COUNT(*) FROM dbo.feeders")).scalar() or 0)
    return {
        "total_feeders": total,
        "sans_poste_source": null_ps,
        "poste_source_inconnu": inconnu,
        "passed": null_ps == 0 and inconnu == 0,
    }


def _interruption_fk_null_rates(session) -> dict[str, Any]:
    ignore_sql = _ignored_interruptions_sql()

    def _rates(where_clause: str = "type_direction = 'distribution'") -> dict[str, Any]:
        row = session.execute(
            text(
                f"""
                SELECT COUNT(*) AS total,
                  SUM(CASE WHEN service_id IS NULL THEN 1 ELSE 0 END) AS sans_service,
                  SUM(CASE WHEN feeder_id IS NULL THEN 1 ELSE 0 END) AS sans_feeder,
                  SUM(CASE WHEN cause_id IS NULL THEN 1 ELSE 0 END) AS sans_cause,
                  SUM(CASE WHEN nature_id IS NULL THEN 1 ELSE 0 END) AS sans_nature,
                  SUM(CASE WHEN siege_id IS NULL THEN 1 ELSE 0 END) AS sans_siege,
                  SUM(CASE WHEN signalisation_id IS NULL THEN 1 ELSE 0 END) AS sans_signalisation
                FROM dbo.interruptions
                WHERE {where_clause}{ignore_sql}
                """
            )
        ).mappings().first()
        total = int(row["total"] or 0)
        details = {k: int(row[k] or 0) for k in row.keys() if k != "total"}
        pct = {
            k: round(100 * v / total, 2) if total else 0.0
            for k, v in details.items()
        }
        return {"total": total, "null_counts": details, "null_pct": pct}

    all_dist = _rates()
    window = _rates(
        "type_direction = 'distribution' "
        "AND date_apparition >= '2020-01-01' AND date_apparition < '2027-01-01'"
    )
    region_broken = int(
        session.execute(
            text(
                """
                SELECT COUNT(*) FROM dbo.interruptions i
                INNER JOIN dbo.services s ON s.id = i.service_id
                LEFT JOIN dbo.agences a ON a.id = s.agence_id
                LEFT JOIN dbo.delegations d ON d.id = a.delegation_id
                LEFT JOIN dbo.regions r ON r.id = d.region_id
                WHERE i.type_direction = 'distribution' AND r.id IS NULL{ignore_sql}
                """
            )
        ).scalar()
        or 0
    )
    # Seuils alignés plan FK : service/cause prioritaires ; feeder dépend des id_maps réseau
    service_pct = window["null_pct"]["sans_service"]
    cause_pct = window["null_pct"]["sans_cause"]
    passed = (
        region_broken == 0
        and service_pct <= 1.0
        and cause_pct <= 10.0
    )
    return {
        "total_distribution": all_dist["total"],
        "null_counts": all_dist["null_counts"],
        "null_pct": all_dist["null_pct"],
        "window_2020_2026": window,
        "region_chain_broken": region_broken,
        "ignored_interruption_ids": sorted(IGNORED_INTERRUPTION_IDS),
        "ignored_interruption_notes": {
            str(k): v for k, v in IGNORED_INTERRUPTION_NOTES.items()
        },
        "thresholds": {
            "sans_service_pct_max": 1.0,
            "sans_cause_pct_max": 10.0,
            "sans_feeder_note": "idfeeder absent de feeders.json ou libellé Feeder vide en HFSQL",
        },
        "passed": passed,
    }


def _rbac_check(session) -> dict[str, int]:
    no_role = session.execute(
        text(
            """
            SELECT COUNT(*) FROM dbo.utilisateurs u
            WHERE u.is_active = 1
            AND NOT EXISTS (
                SELECT 1 FROM dbo.user_roles ur WHERE ur.utilisateur_id = u.id
            )
            """
        )
    ).scalar()
    return {"active_users_without_role": int(no_role or 0)}


def validate() -> dict:
    ensure_dirs()
    report: dict = {
        "generated_at": datetime.now().isoformat(),
        "hfsql_connectivity": test_connection(),
        "checks": {},
        "passed": True,
    }

    source = _source_counts(get_settings().exports_dir)
    report["source_export_counts"] = source

    with get_session() as session:
        target = _target_counts(session)
        report["target_counts"] = target

        count_ok = True
        mapping_tables = {
            "Interruptions": "interruptions",
            "Utilisateurs": "utilisateurs",
            "Feeders": "feeders",
        }
        for src, tgt in mapping_tables.items():
            exp = source.get(src, 0)
            got = target.get(tgt, 0)
            if exp > 0 and got < exp * 0.95:
                count_ok = False
        report["checks"]["counts"] = {"passed": count_ok}

        orphans = _fk_orphans(session)
        fk_ok = all(v == 0 for v in orphans.values())
        report["checks"]["fk_orphans"] = {"details": orphans, "passed": fk_ok}

        end_check = _end_totals(session)
        report["checks"]["end_totals"] = end_check

        saifi_check = _saifi_saidi_check(session)
        report["checks"]["saifi_saidi"] = saifi_check

        rbac = _rbac_check(session)
        rbac_ok = rbac["active_users_without_role"] == 0
        report["checks"]["rbac"] = {**rbac, "passed": rbac_ok}

        fk_null = _interruption_fk_null_rates(session)
        report["checks"]["interruption_fk_null"] = fk_null

        feeder_ps = _feeder_poste_source_check(session)
        report["checks"]["feeder_poste_source"] = feeder_ps

    report["passed"] = all(
        report["checks"][k].get("passed", report["checks"][k].get("within_tolerance", False))
        for k in (
            "counts",
            "fk_orphans",
            "end_totals",
            "saifi_saidi",
            "rbac",
            "interruption_fk_null",
            "feeder_poste_source",
        )
        if k in report["checks"]
    )

    stamp = datetime.now().strftime("%Y%m%d")
    out = get_settings().reports_dir / f"validation_{stamp}.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    report["report_path"] = str(out)
    report["go_no_go"] = "GO" if report["passed"] else "NO-GO"
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Validation post-migration")
    args = parser.parse_args()
    report = validate()
    print(json.dumps(report, indent=2, ensure_ascii=False, default=str))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
