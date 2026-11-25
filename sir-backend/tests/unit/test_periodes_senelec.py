"""Semaine d'exploitation SENELEC (menu « Suivi incidents », étape 2 : fondations).

Règle : une semaine va du samedi au vendredi inclus ; son numéro et son année sont ceux de la
semaine ISO de son vendredi (S43 2026 = 17/10 → 23/10/2026). La « semaine passée » est la
dernière semaine terminée : son vendredi est strictement avant aujourd'hui.

Écrits avant le code (circuit « tests avant le code ») : module attendu ``app.services.periodes``.
"""

import dataclasses
from datetime import date, datetime, timedelta

import pytest

SAMEDI = 5
VENDREDI = 4


# --------------------------------------------------------------------------------------------
# 1. semaine_senelec(jour) : la semaine qui contient le jour
# --------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("jour", "numero", "annee", "debut", "fin"),
    [
        # exemples de la spécification : samedi, mardi, vendredi de S43 ; samedi suivant = S44
        (date(2026, 10, 17), 43, 2026, date(2026, 10, 17), date(2026, 10, 23)),
        (date(2026, 10, 20), 43, 2026, date(2026, 10, 17), date(2026, 10, 23)),
        (date(2026, 10, 23), 43, 2026, date(2026, 10, 17), date(2026, 10, 23)),
        (date(2026, 10, 24), 44, 2026, date(2026, 10, 24), date(2026, 10, 30)),
        # semaine de l'en-tête du rapport hebdo du 21/11/2026
        (date(2026, 11, 14), 47, 2026, date(2026, 11, 14), date(2026, 11, 20)),
        (date(2026, 11, 25), 48, 2026, date(2026, 11, 21), date(2026, 11, 27)),
        # changement d'année : le vendredi 01/01/2027 est en semaine ISO 53 de 2026
        (date(2026, 12, 26), 53, 2026, date(2026, 12, 26), date(2027, 1, 1)),
        (date(2027, 1, 1), 53, 2026, date(2026, 12, 26), date(2027, 1, 1)),
        (date(2027, 1, 2), 1, 2027, date(2027, 1, 2), date(2027, 1, 8)),
        # le vendredi 02/01/2026 est en semaine ISO 1 de 2026 : début de semaine en 2025
        (date(2025, 12, 27), 1, 2026, date(2025, 12, 27), date(2026, 1, 2)),
    ],
)
def test_semaine_senelec_exemples(jour: date, numero: int, annee: int, debut: date, fin: date) -> None:
    """Bornes samedi → vendredi, numéro et année ISO du vendredi."""
    from app.services.periodes import SemaineSenelec, semaine_senelec

    assert semaine_senelec(jour) == SemaineSenelec(numero=numero, annee=annee, debut=debut, fin=fin)


def test_semaine_senelec_regle_generale_sur_deux_ans() -> None:
    """Pour chaque jour de 2026 et 2027 : samedi ≤ jour ≤ vendredi, 7 jours, numéro ISO du vendredi."""
    from app.services.periodes import semaine_senelec

    jour = date(2026, 1, 1)
    while jour <= date(2027, 12, 31):
        s = semaine_senelec(jour)
        assert s.debut.weekday() == SAMEDI, jour
        assert s.fin.weekday() == VENDREDI, jour
        assert s.fin - s.debut == timedelta(days=6), jour
        assert s.debut <= jour <= s.fin, jour
        iso = s.fin.isocalendar()
        assert (s.numero, s.annee) == (iso.week, iso.year), jour
        jour += timedelta(days=1)


def test_semaine_senelec_est_immuable() -> None:
    """SemaineSenelec est une dataclass gelée (valeur, utilisable comme clé)."""
    from app.services.periodes import SemaineSenelec, semaine_senelec

    assert dataclasses.is_dataclass(SemaineSenelec)
    s = semaine_senelec(date(2026, 10, 20))
    with pytest.raises(dataclasses.FrozenInstanceError):
        s.numero = 1  # type: ignore[misc]
    assert hash(s) == hash(semaine_senelec(date(2026, 10, 17)))


# --------------------------------------------------------------------------------------------
# 2. semaine_senelec_passee(aujourd_hui) : la dernière semaine terminée
# --------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("aujourd_hui", "numero", "annee", "debut", "fin"),
    [
        # mercredi 25/11/2026 : dernier vendredi strictement avant = 20/11
        (date(2026, 11, 25), 47, 2026, date(2026, 11, 14), date(2026, 11, 20)),
        # samedi 21/11/2026 : la semaine 14/11 → 20/11 vient de se terminer
        (date(2026, 11, 21), 47, 2026, date(2026, 11, 14), date(2026, 11, 20)),
        # vendredi 20/11/2026 : la semaine en cours n'est pas terminée → 07/11 → 13/11
        (date(2026, 11, 20), 46, 2026, date(2026, 11, 7), date(2026, 11, 13)),
        # changement d'année : mardi 05/01/2027 → semaine du vendredi 01/01/2027 (S53 2026)
        (date(2027, 1, 5), 53, 2026, date(2026, 12, 26), date(2027, 1, 1)),
        # samedi 02/01/2027 : idem
        (date(2027, 1, 2), 53, 2026, date(2026, 12, 26), date(2027, 1, 1)),
        # vendredi 01/01/2027 : semaine précédente, 19/12 → 25/12/2026 (S52)
        (date(2027, 1, 1), 52, 2026, date(2026, 12, 19), date(2026, 12, 25)),
        # samedi 09/01/2027 : première semaine de 2027
        (date(2027, 1, 9), 1, 2027, date(2027, 1, 2), date(2027, 1, 8)),
    ],
)
def test_semaine_senelec_passee_exemples(
    aujourd_hui: date, numero: int, annee: int, debut: date, fin: date
) -> None:
    """Dernière semaine dont le vendredi est strictement avant aujourd'hui."""
    from app.services.periodes import SemaineSenelec, semaine_senelec_passee

    assert semaine_senelec_passee(aujourd_hui) == SemaineSenelec(
        numero=numero, annee=annee, debut=debut, fin=fin
    )


def test_semaine_senelec_passee_regle_generale() -> None:
    """Vendredi < aujourd'hui ≤ vendredi + 7 jours, et c'est une semaine Senelec complète."""
    from app.services.periodes import semaine_senelec, semaine_senelec_passee

    jour = date(2026, 1, 1)
    while jour <= date(2027, 12, 31):
        s = semaine_senelec_passee(jour)
        assert s.fin < jour <= s.fin + timedelta(days=7), jour
        assert semaine_senelec(s.fin) == s, jour
        jour += timedelta(days=1)


def test_semaine_passee_meme_bornes_que_periodes_synthese() -> None:
    """Mêmes bornes que la période « semaine » de la synthèse SAIFI/SAIDI (fin exclue = vendredi + 1)."""
    from app.services.indicateurs_service import periodes_synthese
    from app.services.periodes import semaine_senelec_passee

    jour = date(2026, 1, 1)
    while jour <= date(2027, 12, 31):
        cle, _libelle, debut, fin_exclue = periodes_synthese(jour)[0]
        assert cle == "semaine"
        s = semaine_senelec_passee(jour)
        assert debut == datetime(s.debut.year, s.debut.month, s.debut.day), jour
        assert fin_exclue == datetime(s.fin.year, s.fin.month, s.fin.day) + timedelta(days=1), jour
        jour += timedelta(days=1)
