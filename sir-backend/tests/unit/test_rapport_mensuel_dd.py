"""Rapport mensuel d'exploitation distribution (modèle Analyse succincte PR3-INS-108-a)."""

from datetime import datetime
from itertools import count

from app.repositories.rapport_mensuel_dd_repository import LigneMensuelle
from app.services import rapport_mensuel_dd_service as svc

_ids = count(1)


def ligne(service="SDDV", region="Dakar", feeder="KARMEL", nature="Permanent", cause="Défaut câble",
          siege="Câble", end=1.0, jour=5, mois=9, troncon=None, entreprise=None, duree=60) -> LigneMensuelle:
    return LigneMensuelle(
        id=next(_ids), date_apparition=datetime(2026, mois, jour, 10), date_remise=datetime(2026, mois, jour, 11),
        duree_minutes=duree, service_id=1, service_code=service, region_libelle=region, feeder=feeder,
        nature=nature, cause=cause, siege=siege, entreprise=entreprise, troncon=troncon, end_mwh=end,
    )


def _data(lignes, precedent=(), n1=()):
    return svc.assembler(
        2026, 9, list(lignes), list(precedent), list(n1),
        zones=["Dakar", "Régions"], end_par_mois_mwh=[1.0] * 9, cible_annuelle_mwh=365.0,
        indicateurs=[], defauts=[],
    )


def test_bilan_par_zone_et_nature() -> None:
    data = _data([
        ligne(), ligne(nature="Semi permanent", end=2.0),
        ligne(service="DRS", region="Régions", feeder="BIGNONA", nature="Fugitif", end=0.5),
        ligne(cause="Travaux programmés", nature="Coupure", end=3.0),
        ligne(cause="Délestage production HTB", nature="Délestage", end=9.0),  # HTB : hors bilan HTA
    ])
    assert data.bilan["Dakar"][svc.PERMANENT].nombre == 1
    assert data.bilan["Dakar"][svc.TRAVAUX_HTA].end_mwh == 3.0
    assert data.total.nombre == 4 and data.total.end_mwh == 6.5
    assert [s.code for s in data.services] == ["SDDV", "DRS"]
    assert round(data.cible_mois_mwh, 2) == 30.0  # 365 MWh × 30 j / 365 j


def test_top_departs_sieges_et_evolution() -> None:
    mois = [ligne(feeder="KARMEL") for _ in range(3)] + [ligne(feeder="CICAD", siege="Cellule")]
    prec = [ligne(feeder="KARMEL", mois=8)]
    data = _data(mois, prec)
    top = data.tops["Dakar"][svc.PERMANENT]
    assert [(t.feeder, t.nombre, t.nombre_prec, t.evolution) for t in top] == [("KARMEL", 3, 1, 2), ("CICAD", 1, 0, 1)]
    assert top[0].sieges == {"Câble": 3}
    assert data.sieges_permanents["Dakar"]["SDDV"] == {"Câble": 3, "Cellule": 1}


def test_evolution_m1_et_n1() -> None:
    data = _data([ligne(end=2.0)], [ligne(end=1.0, mois=8)], [ligne(end=4.0)])
    m1 = next(e for e in data.evolution_m1 if e.code == "SDDV")
    assert (m1.nombre_prec, m1.nombre, m1.evolution_pct) == (1, 1, 100.0)
    n1 = next(e for e in data.evolution_n1 if e.code == "SDDV")
    assert n1.evolution_pct == -50.0


def test_troncons_fragilises_et_agressions() -> None:
    lignes = [ligne(troncon="POSTE A - POSTE B") for _ in range(3)] + [ligne(troncon="POSTE C - POSTE D")]
    lignes += [ligne(cause="Agression", entreprise="ERT", end=0.5), ligne(cause="Agression", entreprise=None)]
    data = _data(lignes)
    assert [(t.troncon, t.nombre, t.siege) for t in data.troncons["Dakar"]] == [("POSTE A - POSTE B", 3, "Câble")]
    assert {(a.entreprise, a.nombre) for a in data.agressions["Dakar"]} == {("ERT", 1), ("Tiers", 1)}


def test_synthese_redigee() -> None:
    data = _data([ligne(end=40.0)], [ligne(end=20.0, mois=8)])
    texte = " ".join(data.synthese)
    assert "40\u00a0000 kWh" in texte and "+100,0 %" in texte and "dépassée" in texte
    assert "KARMEL" in texte


def test_requete_sql_server() -> None:
    from sqlalchemy.dialects import mssql

    from app.repositories.rapport_mensuel_dd_repository import requete_lignes

    sql = str(requete_lignes(datetime(2026, 9, 1), datetime(2026, 10, 1)).compile(dialect=mssql.dialect()))
    assert "IS 1" not in sql and "concat" in sql.lower()


def test_exports_pdf_word_excel(tmp_path) -> None:
    from app.services.rapport_mensuel_dd_export import exporter_tout
    from app.services.rapport_mensuel_dd_service import Indicateur

    lignes = [ligne(feeder=f"F{i % 4}", end=0.3 * i, troncon="A - B" if i < 4 else None) for i in range(12)]
    lignes += [ligne(service="DRS", region="Régions", feeder="BIGNONA", nature="Semi permanent", end=1.2),
               ligne(cause="Agression", entreprise="ERT")]
    data = svc.assembler(
        2026, 9, lignes, [ligne(mois=8)], [ligne()], zones=["Dakar", "Régions"],
        end_par_mois_mwh=[5.0] * 9, cible_annuelle_mwh=120.0,
        indicateurs=[Indicateur("Énergie non distribuée HTA", "kWh", 20000.0, cible=9863.0, cumul=45000.0, cible_cumul=89000.0)],
        defauts=[svc.DefautsService("SDDV", 12, 705.4)],
    )
    fichiers = exporter_tout(tmp_path, "rapport", data)
    for ext, chemin in fichiers.items():
        assert chemin.is_file() and chemin.stat().st_size > 2000, ext
    assert fichiers["pdf"].read_bytes().startswith(b"%PDF")
