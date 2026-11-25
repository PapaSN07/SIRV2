"""Catégorie de nature de la Vue d'ensemble « Suivi incidents » (spécification étape 3, §8).

``app.services.suivi_incidents_service.categorie_nature(nature, cause) -> str`` regroupe les
catégories du rapport hebdo DD (``rapport_hebdo_dd_service.categorie``, validées le 29/10) :

| Catégorie hebdo DD                                   | Catégorie suivi |
|------------------------------------------------------|-----------------|
| Permanent, Semi permanent, Fugitif                   | ``incident``    |
| Délestage incident HTA, Délestage HTB / production   | ``delestage``   |
| Travaux réseau HTA                                   | ``travaux``     |
| Manœuvre, Autres coupures HTA, Autres HTB            | ``autre``       |

Écrits avant le code (circuit « tests avant le code »).
"""

from datetime import datetime

import pytest


def _categorie(nature: str | None, cause: str | None) -> str:
    from app.services.suivi_incidents_service import categorie_nature

    return categorie_nature(nature, cause)


@pytest.mark.parametrize(
    ("nature", "cause", "attendu"),
    [
        # incidents : permanent, semi-permanent, fugitif
        ("PERMANENT", "Défaut câble HTA", "incident"),
        ("Permanent", None, "incident"),
        ("SEMI PERMANENT", "Défaut câble HTA", "incident"),
        ("Semi-permanent", None, "incident"),
        ("FUGITIF", "Arbre sur ligne", "incident"),
        ("fugitif", None, "incident"),
        ("  Fugitif  ", None, "incident"),  # espaces de bord ignorés
        # facteur exogène : reste dans sa catégorie
        ("FUGITIF", "Choc accidentel", "incident"),
        # délestages : nature délestage (HTA) ou cause HTB / production avec délestage
        ("DELESTAGE", "Défaut câble HTA", "delestage"),
        ("Délestage", None, "delestage"),
        ("délestage", "surcharge", "delestage"),
        ("Délestage", "Défaut réseau HTB", "delestage"),  # cause HTB + nature délestage
        ("COUPURE", "MANQUE PRODUCTION", "delestage"),  # production → délestage HTB / production
        ("Permanent", "Déficit de production", "delestage"),
        ("Délestage", "BLACK START", "delestage"),
        # travaux : cause « travaux » (nature coupure ou non renseignée), hors HTB
        ("COUPURE", "Travaux d'entretien", "travaux"),
        ("Coupure", "TRAVAUX", "travaux"),
        (None, "travaux programmés", "travaux"),
        # autres : manœuvre, HTB hors délestage, autre nature, rien de renseigné
        ("COUPURE", "Manœuvre réseau", "autre"),
        ("COUPURE", "MANOEUVRE", "autre"),
        ("PERMANENT", "Manœuvre", "autre"),  # la manœuvre l'emporte sur la nature
        ("PERMANENT", "Défaut réseau HTB", "autre"),  # Autres HTB
        ("COUPURE", "Travaux HTB", "autre"),  # travaux sur le HTB : Autres HTB, pas travaux
        ("Coupure", "black start poste", "autre"),
        ("COUPURE", "Défaut câble HTA", "autre"),
        ("COUPURE", None, "autre"),
        ("EFFACEMENT", None, "autre"),
        (None, None, "autre"),
        ("", "", "autre"),
        ("   ", None, "autre"),
    ],
)
def test_categorie_nature(nature: str | None, cause: str | None, attendu: str) -> None:
    """Classement (nature, cause) en incident / delestage / travaux / autre."""
    assert _categorie(nature, cause) == attendu


@pytest.mark.parametrize(
    ("nature", "cause"),
    [
        ("permanent", "défaut htb"),
        ("PERMANENT", "DEFAUT HTB"),
        ("Délestage", "défaut câble hta"),
        ("DELESTAGE", "DEFAUT CABLE HTA"),
        ("coupure", "manœuvre"),
        ("COUPURE", "MANŒUVRE"),
        ("Coupure", "Manoeuvre"),
        ("semi permanent", "travaux"),
    ],
)
def test_accents_et_casse_ignores(nature: str, cause: str) -> None:
    """Même catégorie avec ou sans accents, en majuscules ou en minuscules."""
    assert _categorie(nature, cause) == _categorie(nature.upper(), cause.upper())
    assert _categorie(nature, cause) == _categorie(nature.lower(), cause.lower())


def test_valeurs_possibles() -> None:
    """Seulement les quatre catégories de la Vue d'ensemble."""
    nature_cause = [
        (n, c)
        for n in (None, "PERMANENT", "SEMI PERMANENT", "FUGITIF", "DELESTAGE", "COUPURE", "EFFACEMENT")
        for c in (None, "Défaut câble HTA", "Défaut réseau HTB", "MANQUE PRODUCTION", "Travaux", "Manœuvre")
    ]
    assert {_categorie(n, c) for n, c in nature_cause} == {"incident", "delestage", "travaux", "autre"}


# Correspondance de la spécification : catégorie hebdo DD → catégorie suivi
_CORRESPONDANCE = {
    "permanent": "incident",
    "semi_permanent": "incident",
    "fugitif": "incident",
    "delestage_hta": "delestage",
    "htb_delestage": "delestage",
    "travaux_hta": "travaux",
    "manoeuvre_hta": "autre",
    "autres_hta": "autre",
    "htb_autres": "autre",
}


@pytest.mark.parametrize("nature", [None, "", "PERMANENT", "Semi permanent", "Fugitif", "Délestage", "COUPURE", "EFFACEMENT"])
@pytest.mark.parametrize(
    "cause",
    [
        None, "", "Défaut câble HTA", "Défaut réseau HTB", "MANQUE PRODUCTION", "BLACK START",
        "Travaux d'entretien", "Travaux HTB", "Manœuvre", "Choc accidentel",
    ],
)
def test_derive_du_rapport_hebdo_dd(nature: str | None, cause: str | None) -> None:
    """La catégorie suivi est toujours celle du rapport hebdo DD regroupée (pas un troisième découpage)."""
    from app.repositories.rapport_hebdo_repository import LigneHebdo
    from app.services import rapport_hebdo_dd_service as hebdo

    ligne = LigneHebdo(
        id=1, numero=1, statut="valide", date_apparition=datetime(2026, 11, 14, 8, 0),
        date_remise=datetime(2026, 11, 14, 9, 0), duree_minutes=60, service_id=1, service_code="SDDV",
        region_libelle="DAKAR", feeder="HANN 30KV", nature=nature, cause=cause, end_mwh=0.5,
        clients=100, localisation="x",
    )
    assert set(_CORRESPONDANCE) == {c for c, _ in hebdo.CATEGORIES_HTA} | {c for c, _ in hebdo.CATEGORIES_HTB}
    assert _categorie(nature, cause) == _CORRESPONDANCE[hebdo.categorie(ligne)]
