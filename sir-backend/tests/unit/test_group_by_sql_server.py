"""SQL Server (erreur 8120) : un COALESCE(colonne, ?) en GROUP BY ne correspond pas à celui du SELECT.

Chaque littéral devient un paramètre distinct : regrouper sur la colonne elle-même.
"""

import re
from pathlib import Path

import pytest

FICHIERS = sorted(Path(__file__).resolve().parents[2].joinpath("app").rglob("*.py"))


@pytest.mark.parametrize("fichier", FICHIERS, ids=lambda p: p.name)
def test_pas_de_coalesce_dans_group_by(fichier: Path) -> None:
    texte = re.sub(r"\s+", "", fichier.read_text(encoding="utf-8"))
    assert not re.search(r"group_by\([^)]*func\.coalesce", texte)


def test_categories_sig_sans_distinction_de_casse() -> None:
    """« MIXTE » et « mixte » forment une seule catégorie ; l'expression du GROUP BY est celle du SELECT."""
    from sqlalchemy import func, select
    from sqlalchemy.dialects import mssql

    from app.models.sig import NoeudSig
    from app.repositories.sig_admin_repository import _CATEGORIE

    sql = str(
        select(func.coalesce(_CATEGORIE, "(sans catégorie)"), func.count(NoeudSig.id))
        .group_by(_CATEGORIE)
        .compile(dialect=mssql.dialect())
    )
    assert "GROUP BY upper(trim(dbo.noeuds_sig.categorie))" in sql
    assert "coalesce(upper(trim(dbo.noeuds_sig.categorie))" in sql
