"""Résolution interruption ↔ tronçon SIG (table HFSQL Troncon_SIG)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime


def normalize_troncon_label(text: str | None) -> str:
    if not text:
        return ""
    s = str(text).strip().upper()
    s = re.sub(r"\s*-\s*", "-", s)
    s = re.sub(r"\s+", " ", s)
    return s


def interruption_localisation_keys(localisation: str) -> set[str]:
    """Clés de recherche dérivées de NomTroncon interruption."""
    raw = localisation.strip()
    if not raw:
        return set()
    keys = {normalize_troncon_label(raw)}
    if " - " in raw:
        amont, aval = raw.split(" - ", 1)
        keys.add(normalize_troncon_label(f"{amont.strip()}-{aval.strip()}"))
    return {k for k in keys if k}


@dataclass(frozen=True)
class SigTronconRow:
    id: int
    feeder_id: int | None
    nom_feeder: str | None
    nom_troncon: str | None
    nom_noeud_amont: str | None
    nom_noeud_aval: str | None
    date_chargement: datetime | None


def sig_troncon_keys(row: SigTronconRow) -> set[str]:
    keys: set[str] = set()
    if row.nom_troncon:
        keys.add(normalize_troncon_label(row.nom_troncon))
    if row.nom_noeud_amont and row.nom_noeud_aval:
        keys.add(normalize_troncon_label(f"{row.nom_noeud_amont}-{row.nom_noeud_aval}"))
        keys.add(normalize_troncon_label(f"{row.nom_noeud_amont} - {row.nom_noeud_aval}"))
    return {k for k in keys if k}


def feeder_nom_aliases(libelle: str | None, code: str | None) -> set[str]:
    aliases: set[str] = set()
    for value in (libelle, code):
        if not value:
            continue
        v = value.strip().upper()
        aliases.add(v)
        for suffix in (" 30KV", " 6.6KV", " 6.6", " (D4)"):
            if v.endswith(suffix):
                aliases.add(v[: -len(suffix)].strip())
        for suffix in ("_30KV", "_6_6", "_6.6"):
            if v.endswith(suffix):
                aliases.add(v[: -len(suffix)].strip())
    return {a for a in aliases if a}
