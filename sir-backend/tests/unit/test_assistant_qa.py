"""Assistant : questions en français courant (intention, période, départ cité) et réponses chiffrées."""

from datetime import date, datetime
from types import SimpleNamespace

import pytest
from sqlalchemy import event
from sqlalchemy.dialects import mssql
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.models.geo import Service
from app.models.interruptions import Interruption, InterruptionDistribution, PosteInterruption
from app.models.referentiel import Cause, Nature
from app.models.reseau import Feeder, Poste, PosteSource
from app.repositories import assistant_qa_repository as repo
from app.repositories.lecture_sms_repository import DepartRef
from app.services import assistant_qa_service as qa

AUJ = date(2026, 11, 19)  # jeudi ; semaine DD du samedi 14 au vendredi 20


@pytest.mark.parametrize(
    ("texte", "debut", "fin"),
    [
        ("le poste le plus affecté", datetime(2026, 1, 1), datetime(2026, 11, 20)),
        ("END en octobre", datetime(2026, 10, 1), datetime(2026, 11, 1)),
        ("END en décembre", datetime(2025, 12, 1), datetime(2026, 1, 1)),
        ("SAIFI du mois dernier", datetime(2026, 10, 1), datetime(2026, 11, 1)),
        ("combien hier ?", datetime(2026, 11, 18), datetime(2026, 11, 19)),
        ("semaine dernière", datetime(2026, 11, 7), datetime(2026, 11, 14)),
        ("cette semaine", datetime(2026, 11, 14), datetime(2026, 11, 20)),
        ("les 30 derniers jours", datetime(2026, 10, 21), datetime(2026, 11, 20)),
        ("en 2025", datetime(2025, 1, 1), datetime(2026, 1, 1)),
    ],
)
def test_periodes(texte: str, debut: datetime, fin: datetime) -> None:
    p = qa.lire_periode(texte, AUJ)
    assert (p.debut, p.fin) == (debut, fin)


@pytest.mark.parametrize(
    ("texte", "attendu"),
    [
        ("le poste le plus affecté dans le feeder yeumbeul 30 KV ?", "postes"),
        ("top 5 des départs les plus perturbés", "feeders"),
        ("quelle est l'END du mois dernier", "end"),
        ("SAIDI 2026", "saifi_saidi"),
        ("combien d'interruptions en cours", "en_cours"),
        ("combien à valider", "a_valider"),
        ("principales causes cette semaine", "causes"),
        ("défauts aux 100 km", "defauts_100km"),
        ("quels travaux prioriser ?", None),
        ("dernières interruptions du départ Hann", "recentes"),
        ("bonjour", "resume"),
    ],
)
def test_intentions(texte: str, attendu: str | None) -> None:
    assert qa.intention(" ".join(qa.mots(texte))) == attendu


def test_top() -> None:
    assert qa._top("LE POSTE LE PLUS AFFECTE") == 1
    assert qa._top("TOP 5 DES DEPARTS") == 5
    assert qa._top("LES POSTES LES PLUS TOUCHES") == 10


@pytest.fixture
async def db(monkeypatch: pytest.MonkeyPatch):
    moteur = create_async_engine("sqlite+aiosqlite://", execution_options={"schema_translate_map": {"dbo": None}})
    event.listen(moteur.sync_engine, "connect", lambda c, _: c.create_function("getdate", 0, lambda: "2026-11-19"))
    tables = (Service, PosteSource, Feeder, Poste, Nature, Cause, Interruption, InterruptionDistribution, PosteInterruption)
    async with moteur.begin() as conn:
        for t in tables:
            await conn.run_sync(t.__table__.create)
    async with AsyncSession(moteur) as s:
        s.add_all([
            Service(id=1, agence_id=1, code="SDRBD", libelle="SDRBD", is_active=True),
            PosteSource(id=1, code="TAMBA", libelle="THIAROYE", is_active=True),
            Feeder(id=7, code="YEUMB", libelle="YEUMBEUL 30 KV", poste_source_id=1, service_id=1, is_active=True),
            Feeder(id=8, code="MALIK", libelle="MALIKA", poste_source_id=1, service_id=1, is_active=True),
            Poste(id=1, code="H61A", libelle="H61 PADALAL", feeder_id=7, is_active=True),
            Poste(id=2, code="H61B", libelle="H61 BOW", feeder_id=7, is_active=True),
            Cause(id=1, code="ARB", libelle="Chute d'arbre", type_reseau="distribution", is_active=True),
        ])
        donnees = [(7, [1, 2]), (7, [1]), (7, [1]), (8, [])]
        for i, (feeder, postes) in enumerate(donnees, 1):
            s.add(Interruption(
                id=i, numero_interruption=1000 + i, type_direction="distribution", statut="valide", feeder_id=feeder,
                service_id=1, cause_id=1, is_force_majeure=False, created_by_id=1, duree_minutes=60,
                date_apparition=datetime(2026, 10, i), date_remise=datetime(2026, 10, i, 1),
            ))
            s.add(InterruptionDistribution(interruption_id=i, end_mwh=1.5))
            for p in postes:
                s.add(PosteInterruption(interruption_id=i, poste_id=p, nombre_clients_estime=100))
        await s.commit()
        departs = [DepartRef(7, "YEUMB", "YEUMBEUL 30 KV", 1, "THIAROYE", None), DepartRef(8, "MALIK", "MALIKA", 1, "THIAROYE", None)]

        async def lister_departs(_db):
            return departs

        monkeypatch.setattr(qa.sms_repo, "lister_departs", lister_departs)
        yield s
    await moteur.dispose()


async def test_poste_le_plus_affecte_du_feeder(db: AsyncSession) -> None:
    reponse = await qa.repondre(db, SimpleNamespace(), "le poste le plus affecté dans le feeder yeumbeul 30 KV en octobre ?", None, AUJ)
    assert "H61 PADALAL" in reponse and "3 interruption(s)" in reponse and "YEUMBEUL 30 KV" in reponse


async def test_top_departs_et_end_par_service(db: AsyncSession) -> None:
    reponse = await qa.repondre(db, SimpleNamespace(), "top 2 des départs les plus perturbés en octobre", None, AUJ)
    assert reponse.index("YEUMBEUL") < reponse.index("MALIKA")
    reponse = await qa.repondre(db, SimpleNamespace(), "END d'octobre pour le service SDRBD", None, AUJ)
    assert "6,0 MWh" in reponse


async def test_question_inconnue_donne_l_aide(db: AsyncSession) -> None:
    assert (await qa.repondre(db, SimpleNamespace(), "bonjour", None, AUJ)) == qa.AIDE
    assert (await qa.repondre(db, SimpleNamespace(), "quels travaux prioriser ?", None, AUJ)) is None


def test_requete_postes_sql_server() -> None:
    f = repo.Filtre(datetime(2026, 1, 1), datetime(2026, 2, 1), [1], [7])
    sql = str(
        repo.select(repo.func.count()).where(*repo._conditions(f)).compile(dialect=mssql.dialect())
    )
    assert "date_apparition >=" in sql and "IS 1" not in sql
