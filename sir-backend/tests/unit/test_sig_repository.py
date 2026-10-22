"""Tests unitaires — matching feeder ↔ tronçons SIG."""

from app.models.reseau import Feeder
from app.repositories.sig_repository import _feeder_sig_nom_aliases


def test_feeder_sig_nom_aliases_strips_voltage_suffix() -> None:
    feeder = Feeder(
        id=216,
        code="MERMOZ_30KV",
        libelle="MERMOZ 30KV",
        service_id=1,
        poste_source_id=1,
        is_active=True,
    )
    aliases = _feeder_sig_nom_aliases(feeder)
    assert "MERMOZ 30KV" in aliases
    assert "MERMOZ" in aliases
    assert "MERMOZ_30KV" in aliases
    assert "MERMOZ_SECOURS" not in aliases


def test_feeder_sig_nom_aliases_secours_variant() -> None:
    feeder = Feeder(
        id=219,
        code="MERMOZ_SECOURS_30KV",
        libelle="MERMOZ SECOURS 30KV",
        service_id=1,
        poste_source_id=1,
        is_active=True,
    )
    aliases = _feeder_sig_nom_aliases(feeder)
    assert "MERMOZ SECOURS" in aliases
    assert "MERMOZ" not in aliases
