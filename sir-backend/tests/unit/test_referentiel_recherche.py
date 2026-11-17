"""Liste des référentiels : recherche, statut et tri (compilés pour SQL Server)."""

from sqlalchemy.dialects import mssql

from app.repositories.referentiel_repository import build_select_query


def _sql(**kwargs: object) -> str:
    query = build_select_query("causes", **kwargs)  # type: ignore[arg-type]
    return str(query.compile(dialect=mssql.dialect(), compile_kwargs={"literal_binds": True}))


def test_recherche_plusieurs_mots_sur_code_libelle_description() -> None:
    sql = _sql(recherche="Arbre  50%")
    assert "lower(causes.code) LIKE '%arbre%'" in sql.replace("dbo.", "")
    assert "50\\%" in sql
    assert sql.count(" AND ") >= 1


def test_statut_par_defaut_actifs_et_tous() -> None:
    assert "is_active = 1" in _sql()
    assert "WHERE" not in _sql(statut="tous")
    assert "is_active = 0" in _sql(statut="inactifs")


def test_tri_decroissant_et_colonne_inconnue_ignoree() -> None:
    assert "ORDER BY causes.libelle DESC" in _sql(tri="-libelle").replace("dbo.", "")
    assert "ORDER BY causes.code ASC" in _sql(tri="code").replace("dbo.", "")
    sql = _sql(tri="password_hash").replace("dbo.", "")
    assert "password_hash" not in sql
