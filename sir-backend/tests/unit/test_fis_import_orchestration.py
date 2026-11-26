"""Import FIS — orchestration et traçabilité (tests écrits avant le code).

`fis_import_service.importer_fis(db, contenu, *, current_user, skip_existing=True)` :
- charge les correspondances administrées (`correspondance_fis_repository.dictionnaire`) ;
- appelle `import_fis_file(..., correspondances=<dict>)` ;
- trace chaque interruption créée dans l'historique des statuts (création, et validation si
  le compte peut valider), motif « Import FIS », au nom de l'utilisateur qui importe.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from app.services import fis_import_service as fis

M = "app.services.fis_import_service"
REPO_CORRESP = "app.repositories.correspondance_fis_repository.dictionnaire"
REPO_STATUT = "app.repositories.interruption_statut_repository.ajouter"


def _resultat(creees: list[tuple[int, str]]) -> fis.FisImportResult:
    stats = fis.FisImportStats(total_lignes=len(creees), importees=len(creees))
    return fis.FisImportResult(stats=stats, creees=creees)


async def _orchestrer(creees: list[tuple[int, str]], **kwargs):
    db = MagicMock()
    user = SimpleNamespace(id=7)
    correspondances = {("cause", "chute de météorite"): SimpleNamespace(id=1)}
    resultat = _resultat(creees)
    with (
        patch(REPO_CORRESP, new_callable=AsyncMock, return_value=correspondances) as dictionnaire,
        patch(f"{M}.import_fis_file", new_callable=AsyncMock, return_value=resultat) as importer,
        patch(REPO_STATUT, new_callable=AsyncMock) as ajouter,
    ):
        retour = await fis.importer_fis(db, b"contenu", current_user=user, **kwargs)
    return SimpleNamespace(
        db=db, user=user, correspondances=correspondances, resultat=resultat, retour=retour,
        dictionnaire=dictionnaire, importer=importer, ajouter=ajouter,
    )


async def test_charge_les_correspondances_et_les_transmet() -> None:
    o = await _orchestrer([], skip_existing=False)
    o.dictionnaire.assert_awaited_once()
    assert o.dictionnaire.await_args.args[0] is o.db
    o.importer.assert_awaited_once()
    args, kwargs = o.importer.await_args.args, o.importer.await_args.kwargs
    assert args[0] is o.db
    assert args[1] == b"contenu"
    assert kwargs["current_user"] is o.user
    assert kwargs["skip_existing"] is False
    assert kwargs["correspondances"] is o.correspondances
    assert o.retour is o.resultat


async def test_skip_existing_vrai_par_defaut() -> None:
    o = await _orchestrer([])
    assert o.importer.await_args.kwargs["skip_existing"] is True


async def test_aucune_interruption_creee_aucun_historique() -> None:
    o = await _orchestrer([])
    o.ajouter.assert_not_awaited()


def _appels(ajouter: AsyncMock) -> list[dict]:
    return [c.kwargs for c in ajouter.await_args_list]


async def test_historique_creation_pour_une_interruption_cloturee() -> None:
    o = await _orchestrer([(11, "cloture")])
    appels = _appels(o.ajouter)
    assert len(appels) == 1
    a = appels[0]
    assert o.ajouter.await_args_list[0].args[0] is o.db
    assert a["interruption_id"] == 11
    assert a["action"] == "creation"
    assert a["ancien_statut"] is None
    assert a["nouveau_statut"] == "cloture"
    assert a["utilisateur_id"] == 7
    assert "Import FIS" in (a.get("motif") or "")


async def test_historique_creation_puis_validation_pour_une_interruption_validee() -> None:
    o = await _orchestrer([(12, "valide")])
    appels = _appels(o.ajouter)
    assert [(a["interruption_id"], a["action"]) for a in appels] == [(12, "creation"), (12, "validation")]
    creation, validation = appels
    assert (creation["ancien_statut"], creation["nouveau_statut"]) == (None, "valide")
    assert (validation["ancien_statut"], validation["nouveau_statut"]) == ("cloture", "valide")
    for a in appels:
        assert a["utilisateur_id"] == 7
        assert "Import FIS" in (a.get("motif") or "")


async def test_historique_pour_chaque_interruption_creee() -> None:
    o = await _orchestrer([(11, "cloture"), (12, "valide"), (13, "cloture")])
    appels = _appels(o.ajouter)
    assert [(a["interruption_id"], a["action"]) for a in appels] == [
        (11, "creation"),
        (12, "creation"),
        (12, "validation"),
        (13, "creation"),
    ]
