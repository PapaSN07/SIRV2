"""Croisement END et nombre d'interruptions par nature et par service."""

from app.repositories.indicateurs_repository import NatureServiceRow
from app.services.indicateurs_service import build_nature_service_repartition


def _row(
    nature_code: str,
    nature_libelle: str,
    service_id: int,
    service_code: str,
    nombre: int,
    end_mwh: float,
) -> NatureServiceRow:
    return NatureServiceRow(
        nature_code=nature_code,
        nature_libelle=nature_libelle,
        service_id=service_id,
        service_code=service_code,
        service_libelle=service_code,
        nombre=nombre,
        end_mwh=end_mwh,
    )


def test_build_nature_service_repartition_orders_natures_and_sums() -> None:
    rows = [
        _row("PERMANENT", "Permanent", 2, "SDPG", 2, 0.527),
        _row("COUPURE", "Coupure", 1, "SDDV", 5, 0.703),
        _row("COUPURE", "Coupure", 2, "SDPG", 1, 0.034),
        _row("DELESTAGE", "Délestage", 1, "SDDV", 7, 2.691),
    ]

    result = build_nature_service_repartition(rows)

    assert [service.code for service in result.services] == ["SDDV", "SDPG"]
    assert [ligne.code for ligne in result.lignes] == ["COUPURE", "DELESTAGE", "PERMANENT"]

    coupure = result.lignes[0]
    assert coupure.cellules[0].nombre == 5
    assert coupure.cellules[0].end_kwh == 703
    assert coupure.cellules[1].nombre == 1
    assert coupure.nombre == 6
    assert coupure.end_kwh == 737

    delestage = result.lignes[1]
    assert delestage.cellules[1].nombre == 0
    assert delestage.cellules[1].end_kwh == 0

    assert result.services[0].nombre == 12
    assert result.services[0].end_kwh == 3394
    assert result.services[1].nombre == 3
    assert result.total_nombre == 15
    assert result.total_end_kwh == 3955


def test_build_nature_service_repartition_empty() -> None:
    result = build_nature_service_repartition([])
    assert result.services == []
    assert result.lignes == []
    assert result.total_nombre == 0
    assert result.total_end_kwh == 0
