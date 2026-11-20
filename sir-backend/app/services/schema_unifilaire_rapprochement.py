"""Rapprochement des postes d'un schéma unifilaire avec les postes SIRV2, par le nom.

Pur Python : utilisé par le script d'import et par l'API (« Relancer le rapprochement »).
Un nom porté par plusieurs postes SIRV2 n'est pas rapproché (statut « ambigu ») : un administrateur
choisit le bon poste dans la visionneuse.
"""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from collections.abc import Iterable

# Mots sans valeur pour reconnaître un poste : type de poste, marque de cellule
_MOTS_IGNORES = {"H61", "H59", "POSTE", "CABINE", "PS", "PT", "CM", "C"}


def cle_poste(nom: str | None) -> str:
    """Nom comparable : sans accents ni ponctuation, sans « (400 kVA) », sans « H61 » ni marque « C »."""
    if not nom:
        return ""
    texte = unicodedata.normalize("NFKD", nom).encode("ascii", "ignore").decode().upper()
    texte = re.sub(r"\([^)]*\)", " ", texte)
    texte = re.sub(r"\bH\s*61\b", " ", texte)
    mots = [m for m in re.split(r"[^A-Z0-9]+", texte) if m]
    while mots and mots[0] in _MOTS_IGNORES:
        mots.pop(0)
    while mots and mots[-1] in _MOTS_IGNORES:
        mots.pop()
    return " ".join(mots)


def rapprocher(
    libelles: list[str | None],
    postes: Iterable[tuple[int, str | None, str | None]],
) -> list[tuple[int | None, str | None]]:
    """Pour chaque libellé du schéma : (poste_id, « auto ») si un seul poste SIRV2 porte ce nom,
    (None, « ambigu ») s'il y en a plusieurs, (None, None) sinon."""
    par_cle: dict[str, set[int]] = defaultdict(set)
    par_compacte: dict[str, set[int]] = defaultdict(set)
    for poste_id, libelle, code in postes:
        for nom in (libelle, code):
            cle = cle_poste(nom)
            if cle:
                par_cle[cle].add(poste_id)
                par_compacte[cle.replace(" ", "")].add(poste_id)
    resultat: list[tuple[int | None, str | None]] = []
    for libelle in libelles:
        cle = cle_poste(libelle)
        ids = par_cle.get(cle) or par_compacte.get(cle.replace(" ", "")) if cle else None
        if not ids:
            resultat.append((None, None))
        elif len(ids) == 1:
            resultat.append((next(iter(ids)), "auto"))
        else:
            resultat.append((None, "ambigu"))
    return resultat
