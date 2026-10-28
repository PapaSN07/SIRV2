"""URL de connexion SQL Server."""

from sqlalchemy.engine import make_url


def url_sql_server(url: str) -> str:
    """Active MARS sur SQL Server (plusieurs jeux de résultats par connexion).

    Sans MARS, pyodbc refuse une requête tant que la précédente n'a pas rendu tous ses
    résultats (« Connection is busy with results for another command »). Une valeur
    MARS_Connection déjà présente dans DATABASE_URL est respectée.
    """
    parsed = make_url(url)
    if not parsed.drivername.startswith("mssql"):
        return url
    cles = {k.lower() for k in parsed.query}
    if "mars_connection" in cles or "odbc_connect" in cles:
        return url
    return parsed.update_query_dict({"MARS_Connection": "yes"}).render_as_string(hide_password=False)
