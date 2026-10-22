"""Connexion SQL Server — base IndicateursTransportDistribution (srv-bddomtech)."""

from __future__ import annotations

from urllib.parse import parse_qs, unquote, urlparse

import pyodbc

from scripts.migration.config import get_settings


def _parse_database_url(database_url: str) -> tuple[str, str, str, int, str]:
    parsed = urlparse(database_url.replace("mssql+aioodbc://", "mssql://", 1))
    user = unquote(parsed.username or "")
    password = unquote(parsed.password or "")
    host = parsed.hostname or "localhost"
    port = parsed.port or 1433
    driver = parse_qs(parsed.query).get("driver", ["ODBC Driver 17 for SQL Server"])[0].replace(
        "+", " "
    )
    return user, password, host, port, driver


def build_itd_connection_string(*, database: str | None = None) -> str:
    settings = get_settings()
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL manquant — configurer SIR_PROFILE=senelec")
    user, password, host, port, driver = _parse_database_url(settings.database_url)
    db = database or settings.itd_database
    return (
        f"DRIVER={{{driver}}};SERVER={host},{port};DATABASE={db};"
        f"UID={user};PWD={password};TrustServerCertificate=yes;"
    )


def connect_itd(*, database: str | None = None, timeout: int = 120) -> pyodbc.Connection:
    return pyodbc.connect(build_itd_connection_string(database=database), timeout=timeout)
