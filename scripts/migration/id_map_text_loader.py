"""Reconstruction des id_maps texte depuis les tables référentiel HFSQL."""

from __future__ import annotations

from scripts.migration.hfsql_odbc import load_table_rows
from scripts.migration.id_maps import IdMapStore
from scripts.migration.transforms.codes import text_key
from scripts.migration.transforms.rows import row_get


def rebuild_text_maps(id_maps: IdMapStore) -> dict[str, int]:
    """Remplit services_by_text, causes_by_text, sieges_by_text, signalisations_by_text."""
    counts: dict[str, int] = {}

    for row in load_table_rows("Services"):
        legacy = row_get(row, "IDAUTO", "idauto")
        sir_id = id_maps.get("services", legacy)
        key = text_key(str(row_get(row, "Service", "service") or ""))
        if sir_id and key:
            id_maps.put("services_by_text", key, sir_id)
    counts["services_by_text"] = len(id_maps.load("services_by_text"))

    for table, type_reseau, id_field in (
        ("Causes", "distribution", "IDCauses"),
        ("CausesTransport", "transport", "IDCausesTrans"),
    ):
        for row in load_table_rows(table):
            legacy = row_get(row, id_field, id_field.lower())
            sir_id = id_maps.get("causes", legacy)
            key = text_key(str(row_get(row, "cause", "Cause") or ""))
            if sir_id and key:
                id_maps.put("causes_by_text", f"{type_reseau}:{key}", sir_id)
    counts["causes_by_text"] = len(id_maps.load("causes_by_text"))

    for table, type_reseau, id_field, lib_field in (
        ("Sieges", "distribution", "IDSieges", "Sieges"),
        ("SiegesTransport", "transport", "IDSieges", "Sieges"),
    ):
        for row in load_table_rows(table):
            legacy = row_get(row, id_field, id_field.lower())
            sir_id = id_maps.get("sieges", legacy)
            key = text_key(str(row_get(row, lib_field, lib_field.lower()) or ""))
            if sir_id and key:
                id_maps.put("sieges_by_text", f"{type_reseau}:{key}", sir_id)
    counts["sieges_by_text"] = len(id_maps.load("sieges_by_text"))

    for table, type_reseau, id_field in (
        ("Signalisations", "distribution", "IDSignalisation"),
        ("SignalisationsTransport", "transport", "IDSignalisation"),
    ):
        for row in load_table_rows(table):
            legacy = row_get(row, id_field, id_field.lower())
            sir_id = id_maps.get("signalisations", legacy)
            key = text_key(
                str(row_get(row, "Signalisation", "signalisation") or "")
            )
            if sir_id and key:
                id_maps.put("signalisations_by_text", f"{type_reseau}:{key}", sir_id)
    counts["signalisations_by_text"] = len(id_maps.load("signalisations_by_text"))

    for row in load_table_rows("Feeders"):
        legacy = row_get(row, "IDFeeder", "idfeeder")
        sir_id = id_maps.get("feeders", legacy)
        key = text_key(str(row_get(row, "Feeder", "feeder") or ""))
        if sir_id and key:
            id_maps.put("feeders_by_text", key, sir_id)
    counts["feeders_by_text"] = len(id_maps.load("feeders_by_text"))

    for entity in (
        "services_by_text",
        "causes_by_text",
        "sieges_by_text",
        "signalisations_by_text",
        "feeders_by_text",
    ):
        id_maps.save(entity)

    return counts
