"""Administration → SIG : synthèse, départs (dernier chargement), stations, nœuds (SQLite + SQL Server)."""

from datetime import datetime
from types import SimpleNamespace

import pytest
from sqlalchemy import event
from sqlalchemy.dialects import mssql
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.models.reseau import Feeder, PosteSource
from app.models.sig import FeederSig, NoeudSig, PosteSourceSig, TronconSig
from app.repositories import sig_admin_repository as repo
from app.services import sig_admin_service as svc

ANCIEN, RECENT = datetime(2026, 1, 1), datetime(2026, 10, 1)


@pytest.fixture
async def db():
    moteur = create_async_engine("sqlite+aiosqlite://", execution_options={"schema_translate_map": {"dbo": None}})
    event.listen(moteur.sync_engine, "connect", lambda c, _: c.create_function("getdate", 0, lambda: "2026-11-19"))
    async with moteur.begin() as conn:
        for table in (PosteSource.__table__, Feeder.__table__, NoeudSig.__table__, TronconSig.__table__, PosteSourceSig.__table__, FeederSig.__table__):
            await conn.run_sync(table.create)
    async with AsyncSession(moteur) as session:
        session.add_all([
            PosteSource(id=1, code="HANN", libelle="HANN", is_active=True),
            Feeder(id=10, code="OUAKAM", libelle="OUAKAM", poste_source_id=1, is_active=True),
            # OUAKAM : un ancien chargement (ignoré) et le dernier ; YOFF non rattaché
            TronconSig(legacy_id=1, nom_feeder="OUAKAM", feeder_id=10, nom_troncon="T-old", longueur_m=999, date_chargement=ANCIEN),
            TronconSig(legacy_id=2, nom_feeder="OUAKAM", feeder_id=10, nom_troncon="T1", longueur_m=1500, tension_kv=30, date_chargement=RECENT),
            TronconSig(legacy_id=3, nom_feeder="OUAKAM", feeder_id=10, nom_troncon="T2", longueur_m=500, tension_kv=30, date_chargement=RECENT),
            TronconSig(legacy_id=4, nom_feeder="YOFF", feeder_id=None, nom_troncon="Y1", longueur_m=2000, date_chargement=ANCIEN),
            NoeudSig(legacy_id=1, legacy_fid=1, nom="P OUAKAM 1", nom_feeder="OUAKAM", feeder_id=10, station="HANN", coord_x=237000, coord_y=1627000, categorie="POSTE"),
            NoeudSig(legacy_id=2, legacy_fid=2, nom="PIQUAGE 2", nom_feeder="OUAKAM", feeder_id=10, station="HANN", coord_x=None, coord_y=None, categorie="PIQUAGE"),
            NoeudSig(legacy_id=3, legacy_fid=3, nom="P YOFF", nom_feeder="YOFF", station="12", coord_x=240000, coord_y=1630000, categorie="POSTE"),
            # Station « 12 » des nœuds = identifiant de PosteSource_SIG
            PosteSourceSig(legacy_id="12", nom="CAP DES BICHES", delegation="DRCO"),
            FeederSig(legacy_id="F1", nom="OUAKAM", code="D101", poste_source="HANN", delegation="DD", attributs='{"NOMFEEDER": "OUAKAM"}'),
        ])
        await session.commit()
        yield session
    await moteur.dispose()


_ADMIN = SimpleNamespace(user_roles=[SimpleNamespace(role=SimpleNamespace(nom="SUPERADMIN"))], is_active=True)


@pytest.fixture(autouse=True)
def _droits(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(svc, "_ensure_sig_read", lambda user: None)


async def test_synthese_ne_compte_que_le_dernier_chargement(db: AsyncSession) -> None:
    s = await svc.synthese(db, _ADMIN)  # type: ignore[arg-type]
    assert (s.troncons, s.feeders_sig, s.feeders_rattaches) == (3, 2, 1)
    assert s.longueur_km == 4.0
    assert (s.noeuds, s.noeuds_localises, s.stations) == (3, 2, 2)
    assert {c.categorie: c.nombre for c in s.categories} == {"POSTE": 2, "PIQUAGE": 1}


async def test_feeders_rattachement_et_noeuds(db: AsyncSession) -> None:
    res = await svc.feeders(db, _ADMIN, recherche=None, rattachement=None, page=1, page_size=20)  # type: ignore[arg-type]
    ouakam = next(f for f in res.items if f.nom_feeder == "OUAKAM")
    assert (ouakam.troncons, ouakam.longueur_km, ouakam.noeuds, ouakam.noeuds_localises) == (2, 2.0, 2, 1)
    assert (ouakam.feeder_libelle, ouakam.poste_source_libelle) == ("OUAKAM", "HANN")
    assert (ouakam.code_sig, ouakam.delegation, ouakam.attributs) == ("D101", "DD", {"NOMFEEDER": "OUAKAM"})
    non = await svc.feeders(db, _ADMIN, recherche=None, rattachement="non_rattache", page=1, page_size=20)  # type: ignore[arg-type]
    assert [f.nom_feeder for f in non.items] == ["YOFF"]


async def test_stations_et_noeuds_localises(db: AsyncSession) -> None:
    st = await svc.stations(db, _ADMIN, recherche="hann", page=1, page_size=20)  # type: ignore[arg-type]
    assert st.total == 1 and st.items[0].poste_source_sirv2 == "HANN"
    assert st.items[0].feeders_noms == ["OUAKAM"]
    tous = await svc.stations(db, _ADMIN, recherche=None, page=1, page_size=20)  # type: ignore[arg-type]
    cap = next(s for s in tous.items if s.station == "12")
    assert (cap.nom, cap.delegation, cap.feeders_noms) == ("CAP DES BICHES", "DRCO", ["YOFF"])
    assert abs(st.items[0].latitude - 14.7039) < 1e-3
    nd = await svc.noeuds(db, _ADMIN, recherche=None, nom_feeder="OUAKAM", station=None, categorie=None, localisation="non_localise", tri=None, page=1, page_size=20)  # type: ignore[arg-type]
    assert [n.nom for n in nd.items] == ["PIQUAGE 2"]
    carte = await svc.carte(db, _ADMIN, nom_feeder="OUAKAM", station=None)  # type: ignore[arg-type]
    assert len(carte) == 1 and carte[0].longitude is not None


def test_requetes_compilees_sql_server() -> None:
    query = repo.select(repo.TronconSig.id).where(repo._dernier_chargement())
    sql = str(query.compile(dialect=mssql.dialect()))
    assert "max(" in sql.lower() and "troncons_sig_1" in sql


async def test_defauts_100km_global_service_feeder_nature(db: AsyncSession) -> None:
    from app.models.geo import Service
    from app.models.interruptions import Interruption
    from app.models.referentiel import Nature

    async with db.bind.begin() as conn:  # type: ignore[union-attr]
        for table in (Service.__table__, Nature.__table__, Interruption.__table__):
            await conn.run_sync(table.create)
    db.add_all([
        Service(id=5, agence_id=1, code="SDDV", libelle="SDDV", is_active=True),
        Nature(id=1, code="P", libelle="Permanent", is_active=True),
        Nature(id=2, code="F", libelle="Fugitif", is_active=True),
        Nature(id=3, code="S", libelle="Semi-permanent", is_active=True),
    ])
    feeder = await db.get(Feeder, 10)
    feeder.service_id = 5  # type: ignore[union-attr]
    for i, (nature, fm) in enumerate([(1, False), (1, False), (2, False), (3, False), (2, True)]):
        db.add(Interruption(
            numero_interruption=900 + i, type_direction="distribution", statut="valide", feeder_id=10,
            service_id=5, nature_id=nature, is_force_majeure=fm,
            date_apparition=datetime(2026, 3, 1 + i), date_remise=datetime(2026, 3, 1 + i, 2), created_by_id=1,
        ))
    await db.commit()
    res = await svc.defauts_100km(db, _ADMIN, annee=2026, mois=None)  # type: ignore[arg-type]
    # OUAKAM : 2 km SIG (dernier chargement), 4 défauts hors force majeure dont 2 permanents
    assert (res.global_.defauts, res.global_.permanents, res.global_.longueur_km) == (4, 2, 2.0)
    assert res.global_.defauts_100km == 200.0 and res.global_.permanents_100km == 100.0
    assert res.par_service[0].libelle == "SDDV"
    assert res.par_feeder[0].detail == "HANN · SDDV"
    assert {n.nature: n.defauts for n in res.par_nature} == {"Permanent": 2, "Fugitif": 1, "Semi-permanent": 1}
