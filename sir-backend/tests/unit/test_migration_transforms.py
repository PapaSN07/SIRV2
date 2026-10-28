"""Tests unitaires transforms migration."""

import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2].parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))
elif sys.path[0] != str(_REPO):
    sys.path.remove(str(_REPO))
    sys.path.insert(0, str(_REPO))

from datetime import datetime, time

from scripts.migration.transforms.codes import slug_code, text_key
from scripts.migration.transforms.dates import (
    duration_minutes,
    merge_date_time,
    parse_time,
    resolve_interruption_date_apparition,
    resolve_interruption_date_remise,
)
from scripts.migration.transforms.statut import map_statut


def test_slug_code():
    assert slug_code("Dakar Centre") == "DAKAR_CENTRE"
    assert slug_code("") == "INCONNU"
    assert slug_code("Test", prefix="X") == "XTEST"


def test_text_key():
    assert text_key("  abc  ") == "ABC"
    assert text_key("") is None


def test_merge_date_time():
    d = datetime(2024, 6, 1, 10, 0, 0)
    t = datetime(2024, 1, 1, 14, 30, 0)
    merged = merge_date_time(d, t)
    assert merged == datetime(2024, 6, 1, 14, 30, 0)


def test_duration_minutes():
    assert duration_minutes(120, None, None) == 120
    start = datetime(2024, 1, 1, 10, 0)
    end = datetime(2024, 1, 1, 11, 30)
    assert duration_minutes(None, start, end) == 90


def test_map_statut():
    assert map_statut("En cours") == "en_cours"
    assert map_statut("Clôturé") == "cloture"
    assert map_statut(None, validation=1) == "valide"
    assert map_statut("ok", is_histo=True) == "archive"


def test_resolve_interruption_date_apparition():
    row = {
        "dateapparition": None,
        "heureapparition": time(15, 30),
        "creation": "2019-06-27T15:34:54.252000",
    }
    dt = resolve_interruption_date_apparition(row)
    assert dt == datetime(2019, 6, 27, 15, 30)


def test_resolve_interruption_date_apparition_creation_space_format():
    row = {
        "dateapparition": None,
        "heureapparition": "22:42:00",
        "creation": "2017-06-29 15:45:18.272000",
    }
    dt = resolve_interruption_date_apparition(row)
    assert dt == datetime(2017, 6, 29, 22, 42, 0)


def test_resolve_interruption_date_apparition_modification_fallback():
    row = {
        "heureapparition": "08:15:00",
        "creation": None,
        "modification": "2024-03-10T11:00:00",
    }
    dt = resolve_interruption_date_apparition(row)
    assert dt == datetime(2024, 3, 10, 8, 15, 0)


def test_resolve_interruption_date_apparition_annee_fallback():
    row = {"heureapparition": "14:32:00", "creation": None, "annee": 2017}
    dt = resolve_interruption_date_apparition(row)
    assert dt == datetime(2017, 1, 1, 14, 32, 0)


def test_parse_time_string():
    assert parse_time("15:30:00") == time(15, 30, 0)


def test_resolve_interruption_date_remise():
    row = {"dateremise": None, "heureremise": "14:34:00", "modification": "2017-08-01T10:00:00"}
    assert resolve_interruption_date_remise(row) == datetime(2017, 8, 1, 14, 34, 0)


def test_fk_resolver_legacy_id_priority():
    from scripts.migration.transforms.fk_resolver import FkResolver

    class _Maps:
        def __init__(self) -> None:
            self._data: dict[str, dict[str, int]] = {
                "causes": {"5": 99},
                "causes_by_text": {"distribution:DEFAUT": 42},
                "services": {"3": 7},
                "services_by_text": {"SDDV": 8},
                "feeders": {"12": 55},
                "feeders_by_text": {"FEEDER_A": 56},
            }

        def get(self, entity: str, key) -> int | None:
            if key is None:
                return None
            return self._data.get(entity, {}).get(str(key))

        def lookup_text(self, entity: str, key: str | None) -> int | None:
            return self.get(entity, key)

    fk = FkResolver(_Maps())  # type: ignore[arg-type]
    row = {"idcauses": 5, "Cause": "Autre"}
    assert fk.resolve_cause_id(row) == 99
    row = {"idcauses": 0, "Cause": "Defaut"}
    assert fk.resolve_cause_id(row) == 42
    assert fk.resolve_service_id({"idservice": 3}) == 7
    assert fk.resolve_service_id({"idservice": 0, "Service": "SDDV"}) == 8
    assert fk.resolve_feeder_id({"idfeeder": 12}) == 55
    assert fk.resolve_feeder_id({"idfeeder": 0, "Feeder": "Feeder_A"}) == 56
    assert fk.resolve_feeder_id({"Feeder": "", "feeder2": "Feeder_A"}) == 56


def test_backfill_filter_invalid_fk_ids() -> None:
    from scripts.migration.backfill_interruption_fks import _filter_updates_by_valid_fks

    updates = {1: {"siege_id": 50, "cause_id": 42}, 2: {"siege_id": 3, "cause_id": 99}}
    valid = {
        "service_id": set(),
        "feeder_id": set(),
        "cause_id": {42, 99},
        "nature_id": set(),
        "siege_id": {3, 4},
        "signalisation_id": set(),
    }
    filtered, rejected = _filter_updates_by_valid_fks(updates, valid)
    assert filtered[1] == {"cause_id": 42}
    assert filtered[2] == {"siege_id": 3, "cause_id": 99}
    assert rejected["siege_id"] == 1


def test_duree_minutes_interruption_depuis_duree_heure() -> None:
    """dureeHeure (heures) fait foi ; DureeInterruption n'est plus lue (unité WinDev)."""
    from scripts.migration.transforms.dates import duree_minutes_interruption

    assert duree_minutes_interruption(0.08, None, None) == 5
    assert duree_minutes_interruption("0,05", None, None) == 3
    assert duree_minutes_interruption(0.001, None, None) == 1
    debut, fin = datetime(2026, 5, 1, 8), datetime(2026, 5, 1, 9, 30)
    assert duree_minutes_interruption(0, debut, fin) == 90
    assert duree_minutes_interruption(None, None, None) is None
