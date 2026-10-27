"""SQL Server n'accepte pas `colonne IS 1` : `.is_(True)` est interdit dans le code applicatif."""

import pathlib
import re

APP_DIR = pathlib.Path(__file__).resolve().parents[2] / "app"
MOTIF = re.compile(r"\.(is_|is_not|isnot)\((True|False)\)")


def test_aucun_is_true_dans_le_code() -> None:
    fautifs = [
        f"{p.relative_to(APP_DIR.parent)}:{n}"
        for p in APP_DIR.rglob("*.py")
        for n, ligne in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
        if MOTIF.search(ligne)
    ]
    assert not fautifs, "Utiliser `colonne == true()` (SQL Server rejette `IS 1`) : " + ", ".join(fautifs)
