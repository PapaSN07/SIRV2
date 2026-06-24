"""Mapping statuts interruptions HFSQL → SIR v2."""

from __future__ import annotations

STATUT_MAP = {
    "en cours": "en_cours",
    "encours": "en_cours",
    "ouvert": "en_cours",
    "ouverture": "en_cours",
    "instance": "en_cours",
    "cloture": "cloture",
    "clôturé": "cloture",
    "cloturé": "cloture",
    "clôture": "cloture",
    "ferme": "cloture",
    "fermé": "cloture",
    "valide": "valide",
    "validé": "valide",
    "validation": "valide",
    "archive": "archive",
    "archivé": "archive",
    "historique": "archive",
    "histo": "archive",
}


def map_statut(
    etat_traitement: str | None,
    validation: bool | int | None = None,
    is_histo: bool = False,
) -> str:
    if is_histo:
        return "archive"
    if validation in (True, 1, "1"):
        return "valide"
    if not etat_traitement:
        return "en_cours"
    key = str(etat_traitement).strip().lower()
    for token, statut in STATUT_MAP.items():
        if token in key:
            return statut
    return "en_cours"
