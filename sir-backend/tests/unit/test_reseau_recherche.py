"""Listes réseau : recherche sur les libellés liés (poste source, feeder) et tri par libellé."""

from types import SimpleNamespace

from app.services.reseau_distribution_service import _filtrer_trier, _libelles_feeder, _poste_response


def _feeder(code: str, libelle: str, ps: str | None) -> SimpleNamespace:
    f = SimpleNamespace(code=code, libelle=libelle)
    f.__dict__["poste_source"] = SimpleNamespace(libelle=ps) if ps else None
    f.__dict__["service"] = None
    return f


def test_recherche_par_nom_du_poste_source_et_tri() -> None:
    items = [_feeder("F1", "Ouakam", "Hann"), _feeder("F2", "Yoff", "Cap des Biches"), _feeder("F3", "Almadies", "Hann")]
    res = _filtrer_trier(items, "hann", "-libelle", _libelles_feeder)
    assert [i.code for i in res] == ["F1", "F3"]
    res = _filtrer_trier(items, None, "poste_source_libelle", _libelles_feeder)
    assert [i.code for i in res] == ["F2", "F1", "F3"]


def test_poste_affiche_les_libelles_et_pas_les_identifiants() -> None:
    ps = SimpleNamespace(libelle="Hann")
    feeder = SimpleNamespace(libelle="Ouakam")
    feeder.__dict__["poste_source"] = ps
    poste = SimpleNamespace(
        id=1, code="P1", libelle="Poste 1", feeder_id=3, service_id=None, puissance_kva=None,
        nombre_clients=None, is_active=True,
    )
    poste.__dict__["feeder"] = feeder
    poste.__dict__["service"] = None
    res = _poste_response(poste)  # type: ignore[arg-type]
    assert (res.feeder_libelle, res.poste_source_libelle) == ("Ouakam", "Hann")
