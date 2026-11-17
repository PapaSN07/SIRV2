#!/usr/bin/env python3
"""Génère la police d'icônes réduite de SIRV2 : src/assets/fonts/sir-icones.woff2 (+ .txt).

Pourquoi (10/11/2026) : la police Material Symbols complète pèse 4 Mo ; sur le serveur, les noms
d'icônes s'affichaient en texte (« visibility ») au lieu des icônes. La police réduite aux icônes
du code pèse environ 20 Ko (graisse 400, taille optique 24, GRAD 0 ; FILL 0 à 1 gardé).

À relancer après l'ajout d'une icône dans le code (`npm run verifier-icones` le signale).
Usage, depuis sir-frontend/ :
    pip install fonttools brotli
    python scripts/generer-icones.py
"""

import json
import subprocess
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

RACINE = Path(__file__).resolve().parents[1]
SOURCE = RACINE / "node_modules/material-symbols/material-symbols-outlined.woff2"
SORTIE = RACINE / "src/assets/fonts/sir-icones.woff2"
# Tous les noms reconnus par la police, alias compris (« assessment », « expand_more »…) :
# index.d.ts du paquet n'a que les noms actuels, d'où des icônes oubliées affichées en texte (17/11/2026)
NOMS = RACINE / "scripts/noms-icones.json"


def icones() -> list[str]:
    code = "import('./scripts/icones-utilisees.mjs').then(m => console.log(JSON.stringify(m.iconesUtilisees())))"
    return json.loads(subprocess.check_output(["node", "-e", code], cwd=RACINE, text=True))


def _ligatures(police: TTFont) -> dict[tuple[str, ...], str]:
    ligatures = {}
    for lookup in police["GSUB"].table.LookupList.Lookup:
        for st in lookup.SubTable:
            st = getattr(st, "ExtSubTable", st)
            if st.__class__.__name__ == "LigatureSubst":
                for premier, ligs in st.ligatures.items():
                    for lig in ligs:
                        ligatures[(premier, *lig.Component)] = lig.LigGlyph
    return ligatures


def ecrire_noms() -> None:
    """Liste des noms d'icônes de la police (lue par scripts/icones-utilisees.mjs)."""
    police = TTFont(SOURCE, lazy=False)
    caractere = {glyphe: chr(code) for code, glyphe in police.getBestCmap().items()}
    noms = set()
    for sequence in _ligatures(police):
        if all(g in caractere for g in sequence):
            nom = "".join(caractere[g] for g in sequence)
            if len(nom) > 1 and nom.replace("_", "").isalnum() and nom.islower():
                noms.add(nom)
    NOMS.write_text(json.dumps(sorted(noms)), encoding="utf-8")


def main() -> None:
    ecrire_noms()
    noms = icones()
    police = TTFont(SOURCE, lazy=False)
    cmap = police.getBestCmap()
    ligatures = _ligatures(police)
    glyphes = [ligatures[g] for g in (tuple(cmap.get(ord(c)) for c in n) for n in noms) if g in ligatures]
    options = subset.Options()
    options.layout_features = ["*"]
    options.notdef_outline = True
    options.layout_closure = False
    s = subset.Subsetter(options)
    s.populate(text="abcdefghijklmnopqrstuvwxyz0123456789_ ", glyphs=glyphes)
    s.subset(police)
    police = instancer.instantiateVariableFont(police, {"wght": 400, "GRAD": 0, "opsz": 24})
    police.flavor = "woff2"
    police.save(SORTIE)
    SORTIE.with_suffix(".txt").write_text("\n".join(noms), encoding="utf-8")
    print(f"{len(noms)} icônes, {SORTIE.stat().st_size} octets → {SORTIE}")


if __name__ == "__main__":
    main()
