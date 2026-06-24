"""Accès insensible à la casse aux champs HFSQL (ODBC renvoie souvent des clés lowercase)."""

from __future__ import annotations

from typing import Any


def row_get(row: dict[str, Any], *names: str, default: Any = None) -> Any:
    if not row or not names:
        return default
    lower_map = {str(k).lower(): v for k, v in row.items()}
    for name in names:
        if name in row:
            val = row[name]
            if val is not None or name in row:
                return val
        val = lower_map.get(name.lower())
        if val is not None:
            return val
        if name.lower() in lower_map:
            return lower_map[name.lower()]
    return default


class HfsqlRow(dict):
    """Dict dont .get() ignore la casse des noms de colonnes HFSQL."""

    def get(self, key: str, default: Any = None) -> Any:  # type: ignore[override]
        return row_get(self, key, default=default)


def wrap_row(row: dict[str, Any]) -> HfsqlRow:
    return HfsqlRow(row)
