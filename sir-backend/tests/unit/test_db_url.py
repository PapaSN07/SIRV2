"""MARS activé sur SQL Server (« Connection is busy with results for another command »)."""

from sqlalchemy.dialects.mssql.aioodbc import dialect
from sqlalchemy.engine import make_url

from app.core.db_url import url_sql_server

URL = "mssql+aioodbc://sa:P%40ss!@db:1433/SIR?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes"


def test_mars_ajoute_a_la_chaine_odbc() -> None:
    _, kwargs = dialect().create_connect_args(make_url(url_sql_server(URL)))
    assert "MARS_Connection=yes" in kwargs["dsn"]
    assert "PWD=P@ss!" in kwargs["dsn"]


def test_valeur_existante_respectee() -> None:
    url = URL + "&MARS_Connection=no"
    assert url_sql_server(url) == url


def test_autres_bases_inchangees() -> None:
    assert url_sql_server("sqlite+aiosqlite:///x.db") == "sqlite+aiosqlite:///x.db"
