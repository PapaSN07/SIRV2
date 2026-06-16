"""Defaults SQL Server compatibles (GETDATE au lieu de CURRENT_TIMESTAMP)."""

from sqlalchemy import text

MSSQL_NOW = text("(getdate())")
