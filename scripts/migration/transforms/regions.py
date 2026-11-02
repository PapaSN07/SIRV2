"""Région d'exploitation SIR v1 (colonne « regions » des interruptions) → code région SIRV2."""

from __future__ import annotations

import unicodedata
from typing import Any

# SIR v1 : « Dakar » (BCC) et « Régions » (BRC, toutes les autres régions)
_CODES = {"dakar": "DAKAR", "regions": "REGIONS", "region": "REGIONS"}


def code_region_v1(valeur: Any) -> str | None:
    if valeur is None:
        return None
    texte = (
        unicodedata.normalize("NFKD", str(valeur))
        .encode("ascii", "ignore")
        .decode()
        .strip()
        .lower()
    )
    return _CODES.get(texte)
