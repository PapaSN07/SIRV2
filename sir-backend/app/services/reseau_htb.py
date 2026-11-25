"""Réseau en cause d'une interruption distribution : HTA ou HTB.

Décision SENELEC du 25/11/2026 (règle du rapport hebdo DD) : une interruption distribution
est « HTB » quand le libellé de sa cause contient « HTB », « PRODUCTION » ou « BLACK START »,
sans tenir compte de la casse ni des accents ; « HTA » sinon, y compris sans cause. La même
règle sert partout : rapport hebdo DD, synthèse SAIFI/SAIDI, filtres du suivi incidents.
Équivalent SQL : ``pilotage_repository.condition_reseau``.
"""

from __future__ import annotations

import unicodedata

from app.repositories.pilotage_repository import MOTIFS_CAUSE_HTB


def normaliser_libelle(texte: str | None) -> str:
    """Majuscules sans accents (« Manœuvre » → « MANOEUVRE »), espaces de bord retirés."""
    if not texte:
        return ""
    sans_accent = unicodedata.normalize("NFKD", texte.replace("œ", "oe").replace("Œ", "OE"))
    return "".join(c for c in sans_accent if not unicodedata.combining(c)).upper().strip()


def est_cause_htb(libelle: str | None) -> bool:
    """Vrai quand la cause désigne le réseau HTB (ou la production)."""
    cause = normaliser_libelle(libelle)
    return any(motif in cause for motif in MOTIFS_CAUSE_HTB)
