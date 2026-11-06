"""Aperçu graphique du rapport hebdomadaire DD : catégories, services, jours."""

from datetime import date

from app.services import rapport_hebdo_dd_service as hebdo
from app.services.rapport_apercu_service import construire_apercu_hebdo


def _semaine(debut: date, end_permanent: float, end_sddv: float) -> hebdo.StatsSemaine:
    s = hebdo.StatsSemaine(debut=debut, fin=date.fromordinal(debut.toordinal() + 6), numero=44)
    s.par_categorie[hebdo.PERMANENT] = hebdo.Compte(3, end_permanent)
    s.par_categorie[hebdo.HTB_DELESTAGE] = hebdo.Compte(1, 5.0)
    s.end_service["SDDV"] = end_sddv
    s.end_service["SDRCE"] = 1.0
    s.par_jour[(0, hebdo.PERMANENT, hebdo.DAKAR)] = hebdo.Compte(2, 2.0)
    s.par_jour[(0, hebdo.HTB_DELESTAGE, hebdo.DAKAR)] = hebdo.Compte(1, 5.0)
    s.saifi, s.saidi_h = 0.12, 0.3
    return s


def test_apercu_hebdo() -> None:
    apercu = construire_apercu_hebdo(_semaine(date(2026, 10, 24), 4.0, 3.0), _semaine(date(2026, 10, 17), 2.0, 1.0))
    perm = next(c for c in apercu.categories if c.libelle == "Permanent")
    assert (perm.nombre, perm.end_mwh, perm.end_mwh_precedent) == (3, 4.0, 2.0)
    assert [s.libelle for s in apercu.services] == ["SDDV", "SDRCE"]
    assert apercu.services[0].part_pct == 75.0
    assert len(apercu.jours) == 7 and apercu.jours[0].libelle == "Samedi 24/10"
    assert apercu.jours[0].end_mwh == 2.0  # le HTB n'entre pas dans l'END HTA du jour
    end_hta = next(i for i in apercu.indicateurs if i.libelle.startswith("END"))
    assert (end_hta.valeur, end_hta.precedent) == (4.0, 2.0)
