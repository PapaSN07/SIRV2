"""Import FIS : requêtes de résolution du Référentiel compilées pour SQL Server."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.dialects import mssql

from app.models.referentiel import Cause
from app.services import fis_import_service as fis


async def test_requete_cause_compilee_sql_server() -> None:
    db = MagicMock()
    resultat = MagicMock()
    resultat.scalar_one_or_none.return_value = None
    resultat.scalars.return_value.first.return_value = None
    db.execute = AsyncMock(return_value=resultat)

    with pytest.raises(ValueError):
        await fis._resoudre_referentiel(db, Cause, "Cause", "Agression", "AGRESSION", filtrer_type_reseau=True)

    sqls = [str(c.args[0].compile(dialect=mssql.dialect())) for c in db.execute.await_args_list]
    assert len(sqls) == 2
    for sql in sqls:
        assert "IS 1" not in sql
        assert "is_active = 1" in sql
        assert "type_reseau IN" in sql
    assert "lower(trim(" in sqls[1].lower()
