"""Import FIS : correspondance exacte des libellés et force majeure (relecture du correctif)."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services import fis_import_service as fis


@pytest.mark.parametrize(
    ("libelle", "table"),
    [
        ("défaut semi-permanent", fis.NATURE_LIBELLE_TO_CODE),  # ne doit pas devenir PERMANENT
        ("autre élément bt", fis.SIEGE_LIBELLE_TO_CODE),  # ne doit pas devenir AUTRE
        ("travaux", fis.CAUSE_LIBELLE_TO_CODE),
        ("e", fis.CAUSE_LIBELLE_TO_CODE),
    ],
)
def test_pas_de_correspondance_partielle(libelle: str, table: dict) -> None:
    assert fis._code_depuis_libelle(libelle, table) is None


async def test_force_majeure_suit_le_libelle_fis_meme_si_code_migre_different() -> None:
    """Base migrée : « Agression » a le code DAGRESSION, trouvé par libellé."""
    db = MagicMock()
    par_code = MagicMock()
    par_code.scalar_one_or_none.return_value = None
    par_libelle = MagicMock()
    par_libelle.scalars.return_value.first.return_value = SimpleNamespace(id=3, code="DAGRESSION")
    db.execute = AsyncMock(side_effect=[par_code, par_libelle])

    cause, force_majeure = await fis._get_or_create_cause(db, "Agression")
    assert cause.code == "DAGRESSION"
    assert force_majeure is True
