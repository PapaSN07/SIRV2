"""Injecte schema=dbo dans les opérations Alembic (create/drop table/index)."""

from __future__ import annotations

from alembic.operations.base import Operations

from schema_config import DB_SCHEMA

_PATCHED = False


def patch_alembic_operations(schema: str = DB_SCHEMA) -> None:
    """Applique schema=dbo par défaut sur create/drop table et index."""
    global _PATCHED
    if _PATCHED:
        return

    _orig_create_table = Operations.create_table

    def create_table(self, table_name, *columns, **kw):  # type: ignore[no-untyped-def]
        kw.setdefault("schema", schema)
        return _orig_create_table(self, table_name, *columns, **kw)

    _orig_drop_table = Operations.drop_table

    def drop_table(self, table_name, **kw):  # type: ignore[no-untyped-def]
        kw.setdefault("schema", schema)
        return _orig_drop_table(self, table_name, **kw)

    _orig_create_index = Operations.create_index

    def create_index(self, index_name, table_name, columns, **kw):  # type: ignore[no-untyped-def]
        kw.setdefault("schema", schema)
        return _orig_create_index(self, index_name, table_name, columns, **kw)

    _orig_drop_index = Operations.drop_index

    def drop_index(self, index_name, table_name=None, **kw):  # type: ignore[no-untyped-def]
        kw.setdefault("schema", schema)
        return _orig_drop_index(self, index_name, table_name=table_name, **kw)

    Operations.create_table = create_table  # type: ignore[method-assign]
    Operations.drop_table = drop_table  # type: ignore[method-assign]
    Operations.create_index = create_index  # type: ignore[method-assign]
    Operations.drop_index = drop_index  # type: ignore[method-assign]
    _PATCHED = True
