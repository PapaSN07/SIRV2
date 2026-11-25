"""Tests d'intégration — facteur exogène des causes dans le Référentiel.

Spécification : docs/fusion_suivi_incidents.md, section 12 (25/11/2026).

- ``ReferentielResponse.est_exogene`` : true / false pour les causes, null pour les autres référentiels.
- ``ReferentielCreate.est_exogene`` / ``ReferentielUpdate.est_exogene`` (bool | null) : pris en compte
  pour ``causes`` seulement ; création sans valeur → false ; mise à jour sans valeur → inchangé ;
  valeur envoyée pour un autre référentiel → 422 enveloppé.
- Audit : old_values / new_values de la mise à jour contiennent est_exogene pour une cause.
- Cache du référentiel invalidé (version incrémentée).
- Droits : ceux d'une cause (Admin SCR distribution / commun, Admin Dispatching transport / commun,
  superadmin ; lecture seule ailleurs).

Les tests passent par l'API réelle (routeur → service → repository) ; seules la session (AsyncMock)
et la lecture des enregistrements (``referentiel_repository.get_by_id`` / ``get_by_code``) sont simulées,
pour vérifier ce qui est réellement écrit (instruction UPDATE, objet ajouté, ligne d'audit).
"""

import json
import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.sql.dml import Update

from app.core.security import create_access_token, hash_password
from app.models.audit import AuditLog
from app.models.referentiel import Cause, Nature, Siege
from app.models.utilisateurs import Role, UserRole, Utilisateur
from app.schemas.common import PaginatedResponse

pytestmark = pytest.mark.asyncio

_USER_GET = "app.repositories.utilisateur_repository.get_by_id"
_REF_GET = "app.repositories.referentiel_repository.get_by_id"
_REF_GET_BY_CODE = "app.repositories.referentiel_repository.get_by_code"
_PAGINATE = "app.services.referentiel_service.paginate"


# ---------------------------------------------------------------------------
# Fabriques
# ---------------------------------------------------------------------------


def _make_user(user_id: int, login: str, role_nom: str, role_id: int, scope_service_id: int | None = None) -> Utilisateur:
    role = Role()
    role.id = role_id
    role.nom = role_nom
    role.description = role_nom
    role.is_active = True
    role.role_permissions = []

    ur = UserRole()
    ur.id = 1
    ur.utilisateur_id = user_id
    ur.role_id = role_id
    ur.scope_service_id = scope_service_id
    ur.role = role

    user = Utilisateur()
    user.id = user_id
    user.login = login
    user.password_hash = hash_password("MotDePasse123!")
    user.nom = "Test"
    user.prenom = "User"
    user.email = f"{login}@senelec.sn"
    user.telephone = None
    user.is_active = True
    user.premiere_connexion = False
    user.user_roles = [ur]
    user.audit_logs = []
    ur.utilisateur = user
    return user


def _headers(user: Utilisateur) -> dict[str, str]:
    token = create_access_token(
        subject=str(user.id),
        jti=str(uuid.uuid4()),
        extra={"role": user.user_roles[0].role.nom},
    )
    return {"Authorization": f"Bearer {token}"}


def _cause(
    cause_id: int = 1,
    est_exogene: bool = False,
    type_reseau: str = "distribution",
    libelle: str = "Agression du réseau",
) -> Cause:
    cause = Cause()
    cause.id = cause_id
    cause.code = f"C{cause_id:02d}"
    cause.libelle = libelle
    cause.type_reseau = type_reseau
    cause.is_active = True
    cause.est_exogene = est_exogene
    return cause


def _nature(nature_id: int = 3) -> Nature:
    nature = Nature()
    nature.id = nature_id
    nature.code = "N03"
    nature.libelle = "Coupure"
    nature.is_active = True
    return nature


def _siege(siege_id: int = 4) -> Siege:
    siege = Siege()
    siege.id = siege_id
    siege.code = "S04"
    siege.libelle = "Ligne aérienne"
    siege.type_reseau = "distribution"
    siege.is_active = True
    return siege


def _lecture_avant_apres(mock_db: AsyncMock, avant: Any, apres: Any) -> Any:
    """``get_by_id`` simulé : l'enregistrement d'origine tant qu'aucun UPDATE n'est parti, puis le nouveau."""

    async def _get(_db: Any, _resource: str, _item_id: int) -> Any:
        return apres if mock_db.execute.await_count > 0 else avant

    return _get


def _update_params(mock_db: AsyncMock) -> dict[str, Any]:
    """Valeurs posées par l'instruction UPDATE envoyée à la session (dernier appel)."""
    updates = [c.args[0] for c in mock_db.execute.await_args_list if isinstance(c.args[0], Update)]
    assert updates, "aucune instruction UPDATE envoyée"
    return dict(updates[-1].compile().params)


def _audits(mock_db: AsyncMock) -> list[AuditLog]:
    return [c.args[0] for c in mock_db.add.call_args_list if isinstance(c.args[0], AuditLog)]


@pytest.fixture
def admin_scr() -> Utilisateur:
    return _make_user(2, "admin_scr", "ADMIN_SCR", 2)


@pytest.fixture
def admin_dispatching() -> Utilisateur:
    return _make_user(3, "admin_disp", "ADMIN_DISPATCHING", 3)


@pytest.fixture
def admin_saqs() -> Utilisateur:
    return _make_user(4, "admin_saqs", "ADMIN_SAQS", 4)


@pytest.fixture
def bcc_user() -> Utilisateur:
    return _make_user(1, "bcc_user", "BCC", 1, scope_service_id=1)


@pytest.fixture
def superadmin() -> Utilisateur:
    return _make_user(9, "superadmin", "SUPERADMIN", 9)


@pytest.fixture
def db(mock_db: AsyncMock) -> AsyncMock:
    """Session simulée dont ``add`` est synchrone (comme ``AsyncSession.add``)."""
    mock_db.add = MagicMock()

    async def _refresh(record: Any) -> None:
        if getattr(record, "id", None) is None:
            record.id = 50

    mock_db.refresh = AsyncMock(side_effect=_refresh)
    return mock_db


# ---------------------------------------------------------------------------
# Lecture : est_exogene dans la réponse
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("valeur", [True, False])
async def test_get_cause_renvoie_est_exogene(
    client: AsyncClient, db: AsyncMock, bcc_user: Utilisateur, valeur: bool
) -> None:
    with patch(_USER_GET, return_value=bcc_user), patch(
        _REF_GET, new_callable=AsyncMock, return_value=_cause(est_exogene=valeur)
    ):
        response = await client.get("/api/v1/referentiel/causes/1", headers=_headers(bcc_user))

    assert response.status_code == 200
    data = response.json()["data"]
    assert "est_exogene" in data
    assert data["est_exogene"] is valeur


@pytest.mark.parametrize(
    ("resource", "record"),
    [("natures", _nature()), ("sieges", _siege())],
)
async def test_get_autre_referentiel_renvoie_est_exogene_null(
    client: AsyncClient, db: AsyncMock, bcc_user: Utilisateur, resource: str, record: Any
) -> None:
    with patch(_USER_GET, return_value=bcc_user), patch(_REF_GET, new_callable=AsyncMock, return_value=record):
        response = await client.get(f"/api/v1/referentiel/{resource}/{record.id}", headers=_headers(bcc_user))

    assert response.status_code == 200
    data = response.json()["data"]
    assert "est_exogene" in data
    assert data["est_exogene"] is None


async def test_liste_des_causes_renvoie_est_exogene_et_le_met_en_cache(
    client: AsyncClient, db: AsyncMock, fake_redis: Any, bcc_user: Utilisateur
) -> None:
    page = PaginatedResponse(
        items=[_cause(1, est_exogene=True), _cause(2, est_exogene=False)], total=2, page=1, page_size=20
    )
    with patch(_USER_GET, return_value=bcc_user), patch(_PAGINATE, new_callable=AsyncMock, return_value=page):
        response = await client.get("/api/v1/referentiel/causes", headers=_headers(bcc_user))
        # Deuxième appel servi par le cache Redis : le drapeau doit y survivre
        response_cache = await client.get("/api/v1/referentiel/causes", headers=_headers(bcc_user))

    assert response.status_code == 200
    items = response.json()["data"]["items"]
    assert [i["est_exogene"] for i in items] == [True, False]
    assert [i["est_exogene"] for i in response_cache.json()["data"]["items"]] == [True, False]


# ---------------------------------------------------------------------------
# Création
# ---------------------------------------------------------------------------


async def test_post_cause_avec_est_exogene_true(
    client: AsyncClient, db: AsyncMock, admin_scr: Utilisateur
) -> None:
    with patch(_USER_GET, return_value=admin_scr), patch(_REF_GET_BY_CODE, new_callable=AsyncMock, return_value=None):
        response = await client.post(
            "/api/v1/referentiel/causes",
            headers=_headers(admin_scr),
            json={"code": "C77", "libelle": "Malveillance", "type_reseau": "distribution", "est_exogene": True},
        )

    assert response.status_code == 201, response.text
    assert response.json()["data"]["est_exogene"] is True
    causes_ajoutees = [c.args[0] for c in db.add.call_args_list if isinstance(c.args[0], Cause)]
    assert len(causes_ajoutees) == 1
    assert causes_ajoutees[0].est_exogene is True


async def test_post_cause_sans_est_exogene_vaut_false(
    client: AsyncClient, db: AsyncMock, admin_scr: Utilisateur
) -> None:
    with patch(_USER_GET, return_value=admin_scr), patch(_REF_GET_BY_CODE, new_callable=AsyncMock, return_value=None):
        response = await client.post(
            "/api/v1/referentiel/causes",
            headers=_headers(admin_scr),
            json={"code": "C78", "libelle": "Défaut matériel", "type_reseau": "distribution"},
        )

    assert response.status_code == 201, response.text
    assert response.json()["data"]["est_exogene"] is False
    causes_ajoutees = [c.args[0] for c in db.add.call_args_list if isinstance(c.args[0], Cause)]
    assert len(causes_ajoutees) == 1
    # Posé explicitement par l'application (le default SQLAlchemy ne s'applique qu'à l'INSERT)
    assert causes_ajoutees[0].est_exogene is False


async def test_post_nature_sans_est_exogene_renvoie_null(
    client: AsyncClient, db: AsyncMock, admin_scr: Utilisateur
) -> None:
    with patch(_USER_GET, return_value=admin_scr), patch(_REF_GET_BY_CODE, new_callable=AsyncMock, return_value=None):
        response = await client.post(
            "/api/v1/referentiel/natures",
            headers=_headers(admin_scr),
            json={"code": "N09", "libelle": "Travaux"},
        )

    assert response.status_code == 201, response.text
    assert "est_exogene" in response.json()["data"]
    assert response.json()["data"]["est_exogene"] is None


@pytest.mark.parametrize(
    ("resource", "payload"),
    [
        ("natures", {"code": "N10", "libelle": "Travaux", "est_exogene": True}),
        ("sieges", {"code": "S10", "libelle": "Câble", "type_reseau": "distribution", "est_exogene": False}),
    ],
)
async def test_post_autre_referentiel_avec_est_exogene_renvoie_422_enveloppe(
    client: AsyncClient,
    db: AsyncMock,
    fake_redis: Any,
    admin_scr: Utilisateur,
    resource: str,
    payload: dict[str, Any],
) -> None:
    with patch(_USER_GET, return_value=admin_scr), patch(_REF_GET_BY_CODE, new_callable=AsyncMock, return_value=None):
        response = await client.post(f"/api/v1/referentiel/{resource}", headers=_headers(admin_scr), json=payload)

    assert response.status_code == 422, response.text
    erreur = response.json()["detail"]
    assert erreur["status"] == "error"
    assert erreur["data"] is None
    assert "cause" in erreur["error"].lower()
    db.add.assert_not_called()
    assert await fake_redis.get(f"referentiel:{resource}:version") is None


# ---------------------------------------------------------------------------
# Mise à jour (PUT — seule méthode de modification du routeur)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("avant", "apres"), [(False, True), (True, False)])
async def test_put_cause_change_est_exogene(
    client: AsyncClient, db: AsyncMock, admin_scr: Utilisateur, avant: bool, apres: bool
) -> None:
    lecture = _lecture_avant_apres(db, _cause(est_exogene=avant), _cause(est_exogene=apres))
    with patch(_USER_GET, return_value=admin_scr), patch(_REF_GET, side_effect=lecture):
        response = await client.put(
            "/api/v1/referentiel/causes/1", headers=_headers(admin_scr), json={"est_exogene": apres}
        )

    assert response.status_code == 200, response.text
    assert response.json()["data"]["est_exogene"] is apres
    assert _update_params(db).get("est_exogene", "absent") is apres


async def test_put_cause_sans_est_exogene_ne_le_modifie_pas(
    client: AsyncClient, db: AsyncMock, admin_scr: Utilisateur
) -> None:
    lecture = _lecture_avant_apres(
        db, _cause(est_exogene=True), _cause(est_exogene=True, libelle="Agression (tiers)")
    )
    with patch(_USER_GET, return_value=admin_scr), patch(_REF_GET, side_effect=lecture), patch(
        _REF_GET_BY_CODE, new_callable=AsyncMock, return_value=None
    ):
        response = await client.put(
            "/api/v1/referentiel/causes/1", headers=_headers(admin_scr), json={"libelle": "Agression (tiers)"}
        )

    assert response.status_code == 200, response.text
    params = _update_params(db)
    assert "est_exogene" not in params
    assert params["libelle"] == "Agression (tiers)"
    assert response.json()["data"]["est_exogene"] is True


@pytest.mark.parametrize(
    ("resource", "record", "payload"),
    [
        ("natures", _nature(), {"est_exogene": True}),
        ("sieges", _siege(), {"est_exogene": False}),
        ("natures", _nature(), {"libelle": "Coupure programmée", "est_exogene": False}),
    ],
)
async def test_put_autre_referentiel_avec_est_exogene_renvoie_422_enveloppe(
    client: AsyncClient,
    db: AsyncMock,
    fake_redis: Any,
    admin_scr: Utilisateur,
    resource: str,
    record: Any,
    payload: dict[str, Any],
) -> None:
    with patch(_USER_GET, return_value=admin_scr), patch(_REF_GET, new_callable=AsyncMock, return_value=record), patch(
        _REF_GET_BY_CODE, new_callable=AsyncMock, return_value=None
    ):
        response = await client.put(
            f"/api/v1/referentiel/{resource}/{record.id}", headers=_headers(admin_scr), json=payload
        )

    assert response.status_code == 422, response.text
    erreur = response.json()["detail"]
    assert erreur["status"] == "error"
    assert erreur["data"] is None
    assert "cause" in erreur["error"].lower()
    db.execute.assert_not_awaited()
    assert _audits(db) == []
    assert await fake_redis.get(f"referentiel:{resource}:version") is None


async def test_put_nature_avec_est_exogene_null_est_accepte(
    client: AsyncClient, db: AsyncMock, admin_scr: Utilisateur
) -> None:
    """null = « pas de valeur » : pas de 422 (point tranché, la spécification parle d'une valeur envoyée)."""
    renommee = _nature()
    renommee.libelle = "Coupure programmée"
    lecture = _lecture_avant_apres(db, _nature(), renommee)
    with patch(_USER_GET, return_value=admin_scr), patch(_REF_GET, side_effect=lecture), patch(
        _REF_GET_BY_CODE, new_callable=AsyncMock, return_value=None
    ):
        response = await client.put(
            "/api/v1/referentiel/natures/3",
            headers=_headers(admin_scr),
            json={"libelle": "Coupure programmée", "est_exogene": None},
        )

    assert response.status_code == 200, response.text
    assert response.json()["data"]["est_exogene"] is None
    assert "est_exogene" not in _update_params(db)


# ---------------------------------------------------------------------------
# Audit et cache
# ---------------------------------------------------------------------------


async def test_put_cause_audit_contient_est_exogene(
    client: AsyncClient, db: AsyncMock, admin_scr: Utilisateur
) -> None:
    lecture = _lecture_avant_apres(db, _cause(est_exogene=False), _cause(est_exogene=True))
    with patch(_USER_GET, return_value=admin_scr), patch(_REF_GET, side_effect=lecture):
        response = await client.put(
            "/api/v1/referentiel/causes/1", headers=_headers(admin_scr), json={"est_exogene": True}
        )

    assert response.status_code == 200, response.text
    audits = [a for a in _audits(db) if a.action == "update"]
    assert len(audits) == 1
    audit = audits[0]
    assert audit.table_name == "causes"
    assert audit.record_id == 1
    assert audit.user_id == admin_scr.id
    assert json.loads(audit.old_values)["est_exogene"] is False
    assert json.loads(audit.new_values)["est_exogene"] is True


async def test_put_nature_audit_sans_est_exogene(
    client: AsyncClient, db: AsyncMock, admin_scr: Utilisateur
) -> None:
    """Garde : le drapeau n'apparaît dans l'audit que pour une cause."""
    renommee = _nature()
    renommee.libelle = "Coupure programmée"
    lecture = _lecture_avant_apres(db, _nature(), renommee)
    with patch(_USER_GET, return_value=admin_scr), patch(_REF_GET, side_effect=lecture), patch(
        _REF_GET_BY_CODE, new_callable=AsyncMock, return_value=None
    ):
        response = await client.put(
            "/api/v1/referentiel/natures/3", headers=_headers(admin_scr), json={"libelle": "Coupure programmée"}
        )

    assert response.status_code == 200, response.text
    audit = [a for a in _audits(db) if a.action == "update"][0]
    assert "est_exogene" not in json.loads(audit.old_values)
    assert "est_exogene" not in json.loads(audit.new_values)


async def test_put_cause_est_exogene_invalide_le_cache(
    client: AsyncClient, db: AsyncMock, fake_redis: Any, admin_scr: Utilisateur
) -> None:
    await fake_redis.set("referentiel:causes:version", "0")
    lecture = _lecture_avant_apres(db, _cause(est_exogene=False), _cause(est_exogene=True))
    with patch(_USER_GET, return_value=admin_scr), patch(_REF_GET, side_effect=lecture):
        response = await client.put(
            "/api/v1/referentiel/causes/1", headers=_headers(admin_scr), json={"est_exogene": True}
        )

    assert response.status_code == 200, response.text
    assert _update_params(db).get("est_exogene") is True
    assert await fake_redis.get("referentiel:causes:version") == "1"


# ---------------------------------------------------------------------------
# Droits (RBAC) : rôle autorisé dans son périmètre, même rôle hors périmètre,
# rôles non autorisés, rôle national
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("type_reseau", ["distribution", "commun"])
async def test_admin_scr_modifie_est_exogene_cause_distribution_ou_commune(
    client: AsyncClient, db: AsyncMock, admin_scr: Utilisateur, type_reseau: str
) -> None:
    lecture = _lecture_avant_apres(
        db, _cause(est_exogene=False, type_reseau=type_reseau), _cause(est_exogene=True, type_reseau=type_reseau)
    )
    with patch(_USER_GET, return_value=admin_scr), patch(_REF_GET, side_effect=lecture):
        response = await client.put(
            "/api/v1/referentiel/causes/1", headers=_headers(admin_scr), json={"est_exogene": True}
        )

    assert response.status_code == 200, response.text
    assert response.json()["data"]["est_exogene"] is True
    assert _update_params(db).get("est_exogene") is True


async def test_admin_scr_ne_modifie_pas_est_exogene_cause_transport(
    client: AsyncClient, db: AsyncMock, fake_redis: Any, admin_scr: Utilisateur
) -> None:
    with patch(_USER_GET, return_value=admin_scr), patch(
        _REF_GET, new_callable=AsyncMock, return_value=_cause(type_reseau="transport")
    ):
        response = await client.put(
            "/api/v1/referentiel/causes/1", headers=_headers(admin_scr), json={"est_exogene": True}
        )

    assert response.status_code == 403
    db.execute.assert_not_awaited()
    assert await fake_redis.get("referentiel:causes:version") is None


async def test_admin_dispatching_modifie_est_exogene_cause_transport(
    client: AsyncClient, db: AsyncMock, admin_dispatching: Utilisateur
) -> None:
    lecture = _lecture_avant_apres(
        db, _cause(est_exogene=False, type_reseau="transport"), _cause(est_exogene=True, type_reseau="transport")
    )
    with patch(_USER_GET, return_value=admin_dispatching), patch(_REF_GET, side_effect=lecture):
        response = await client.put(
            "/api/v1/referentiel/causes/1", headers=_headers(admin_dispatching), json={"est_exogene": True}
        )

    assert response.status_code == 200, response.text
    assert response.json()["data"]["est_exogene"] is True
    assert _update_params(db).get("est_exogene") is True


async def test_admin_dispatching_ne_modifie_pas_est_exogene_cause_distribution(
    client: AsyncClient, db: AsyncMock, fake_redis: Any, admin_dispatching: Utilisateur
) -> None:
    with patch(_USER_GET, return_value=admin_dispatching), patch(
        _REF_GET, new_callable=AsyncMock, return_value=_cause(type_reseau="distribution")
    ):
        response = await client.put(
            "/api/v1/referentiel/causes/1", headers=_headers(admin_dispatching), json={"est_exogene": True}
        )

    assert response.status_code == 403
    db.execute.assert_not_awaited()
    assert await fake_redis.get("referentiel:causes:version") is None


@pytest.mark.parametrize("role_fixture", ["admin_saqs", "bcc_user"])
async def test_roles_non_autorises_ne_modifient_pas_est_exogene(
    client: AsyncClient,
    db: AsyncMock,
    fake_redis: Any,
    request: pytest.FixtureRequest,
    role_fixture: str,
) -> None:
    user: Utilisateur = request.getfixturevalue(role_fixture)
    with patch(_USER_GET, return_value=user), patch(
        _REF_GET, new_callable=AsyncMock, return_value=_cause(type_reseau="distribution")
    ):
        response = await client.put(
            "/api/v1/referentiel/causes/1", headers=_headers(user), json={"est_exogene": True}
        )
        response_post = await client.post(
            "/api/v1/referentiel/causes",
            headers=_headers(user),
            json={"code": "C79", "libelle": "Choc", "type_reseau": "distribution", "est_exogene": True},
        )

    assert response.status_code == 403
    assert response_post.status_code == 403
    db.execute.assert_not_awaited()
    db.add.assert_not_called()
    assert await fake_redis.get("referentiel:causes:version") is None


async def test_superadmin_national_modifie_est_exogene_de_toute_cause(
    client: AsyncClient, db: AsyncMock, superadmin: Utilisateur
) -> None:
    lecture = _lecture_avant_apres(
        db, _cause(est_exogene=False, type_reseau="transport"), _cause(est_exogene=True, type_reseau="transport")
    )
    with patch(_USER_GET, return_value=superadmin), patch(_REF_GET, side_effect=lecture):
        response = await client.put(
            "/api/v1/referentiel/causes/1", headers=_headers(superadmin), json={"est_exogene": True}
        )

    assert response.status_code == 200, response.text
    assert response.json()["data"]["est_exogene"] is True
    assert _update_params(db).get("est_exogene") is True
