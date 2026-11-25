"""Tests d'intégration — droits de modification d'un élément du Référentiel selon son réseau.

Faille corrigée (25/11/2026) : ``referentiel_service.update_item`` vérifiait le droit d'écriture sur le
réseau ENVOYÉ (``body.type_reseau or record.type_reseau``) et non sur le réseau actuel de l'élément.
Un Admin Dispatching pouvait donc déplacer une cause distribution en transport (et la modifier).

Contrat (référentiels portant un ``type_reseau`` : causes, sieges, signalisations) :

- le droit (``_ensure_can_write``) est vérifié sur le réseau ACTUEL de l'élément s'il en a un ;
- il est AUSSI vérifié sur le NOUVEAU réseau s'il est envoyé et différent de l'actuel ;
- élément sans réseau actuel : vérification sur le nouveau réseau s'il est envoyé, sinon 422
  « type_reseau obligatoire » (comportement actuel) ;
- refus → 403 enveloppé ``{"status": "error", "data": null, "error": ...}``, sans aucune écriture :
  pas d'UPDATE, pas de ligne d'audit, version du cache ``referentiel:{resource}:version`` inchangée ;
- matrice : Admin SCR → distribution et commun ; Admin Dispatching → transport et commun ;
  superadmin → tout ; natures / types_end sans type_reseau (les deux admins) ;
- la suppression (``delete_item``) vérifie déjà le réseau actuel : non-régression.

Les tests passent par l'API réelle (routeur → service → repository) ; seules la session (AsyncMock)
et la lecture des enregistrements (``referentiel_repository.get_by_id`` / ``get_by_code``) sont simulées.
"""

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.sql.dml import Update

from app.core.security import create_access_token, hash_password
from app.models.audit import AuditLog
from app.models.referentiel import Cause, Nature, Siege, Signalisation
from app.models.utilisateurs import Role, UserRole, Utilisateur

pytestmark = pytest.mark.asyncio

_USER_GET = "app.repositories.utilisateur_repository.get_by_id"
_REF_GET = "app.repositories.referentiel_repository.get_by_id"
_REF_GET_BY_CODE = "app.repositories.referentiel_repository.get_by_code"


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


def _cause(type_reseau: str | None, libelle: str = "Agression du réseau", cause_id: int = 1) -> Cause:
    cause = Cause()
    cause.id = cause_id
    cause.code = f"C{cause_id:02d}"
    cause.libelle = libelle
    cause.type_reseau = type_reseau  # None : donnée ancienne sans réseau (simulée)
    cause.is_active = True
    cause.est_exogene = False
    return cause


def _siege(type_reseau: str | None, libelle: str = "Ligne aérienne", siege_id: int = 4) -> Siege:
    siege = Siege()
    siege.id = siege_id
    siege.code = f"S{siege_id:02d}"
    siege.libelle = libelle
    siege.type_reseau = type_reseau
    siege.is_active = True
    return siege


def _signalisation(type_reseau: str | None, libelle: str = "Déclenchement", sig_id: int = 5) -> Signalisation:
    sig = Signalisation()
    sig.id = sig_id
    sig.code = f"G{sig_id:02d}"
    sig.libelle = libelle
    sig.type_reseau = type_reseau
    sig.is_active = True
    return sig


def _nature(libelle: str = "Coupure", nature_id: int = 3) -> Nature:
    nature = Nature()
    nature.id = nature_id
    nature.code = "N03"
    nature.libelle = libelle
    nature.is_active = True
    return nature


_FABRIQUES = {"causes": _cause, "sieges": _siege, "signalisations": _signalisation}


def _lecture_avant_apres(mock_db: AsyncMock, avant: Any, apres: Any) -> Any:
    """``get_by_id`` simulé : l'enregistrement d'origine tant qu'aucun UPDATE n'est parti, puis le nouveau."""

    async def _get(_db: Any, _resource: str, _item_id: int) -> Any:
        return apres if mock_db.execute.await_count > 0 else avant

    return _get


def _updates(mock_db: AsyncMock) -> list[Update]:
    return [c.args[0] for c in mock_db.execute.await_args_list if isinstance(c.args[0], Update)]


def _update_params(mock_db: AsyncMock) -> dict[str, Any]:
    updates = _updates(mock_db)
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
    return mock_db


async def _put(
    client: AsyncClient,
    db: AsyncMock,
    user: Utilisateur,
    resource: str,
    avant: Any,
    apres: Any,
    payload: dict[str, Any],
) -> Any:
    lecture = _lecture_avant_apres(db, avant, apres)
    with patch(_USER_GET, return_value=user), patch(_REF_GET, side_effect=lecture), patch(
        _REF_GET_BY_CODE, new_callable=AsyncMock, return_value=None
    ):
        return await client.put(f"/api/v1/referentiel/{resource}/{avant.id}", headers=_headers(user), json=payload)


async def _assert_refus_sans_ecriture(response: Any, db: AsyncMock, fake_redis: Any, resource: str) -> None:
    assert response.status_code == 403, response.text
    erreur = response.json()["detail"]
    assert erreur["status"] == "error"
    assert erreur["data"] is None
    assert erreur["error"]
    assert _updates(db) == [], "aucun UPDATE ne doit partir après un refus"
    db.execute.assert_not_awaited()
    assert _audits(db) == []
    db.add.assert_not_called()
    assert await fake_redis.get(f"referentiel:{resource}:version") is None


async def _assert_modifie(response: Any, db: AsyncMock, fake_redis: Any, resource: str, nouveau_type: str | None) -> None:
    assert response.status_code == 200, response.text
    params = _update_params(db)
    if nouveau_type is not None:
        assert params.get("type_reseau") == nouveau_type
        assert response.json()["data"]["type_reseau"] == nouveau_type
    assert len([a for a in _audits(db) if a.action == "update"]) == 1
    assert await fake_redis.get(f"referentiel:{resource}:version") == "1"


# ---------------------------------------------------------------------------
# Changement de réseau refusé : réseau actuel hors périmètre (cœur de la faille)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "payload",
    [
        {"type_reseau": "transport"},
        {"type_reseau": "transport", "libelle": "Agression (tiers)"},
        {"type_reseau": "transport", "est_exogene": True},
    ],
)
async def test_admin_dispatching_ne_deplace_pas_cause_distribution_en_transport(
    client: AsyncClient, db: AsyncMock, fake_redis: Any, admin_dispatching: Utilisateur, payload: dict[str, Any]
) -> None:
    response = await _put(
        client, db, admin_dispatching, "causes", _cause("distribution"), _cause("transport"), payload
    )
    await _assert_refus_sans_ecriture(response, db, fake_redis, "causes")


async def test_admin_dispatching_ne_deplace_pas_cause_distribution_en_commun(
    client: AsyncClient, db: AsyncMock, fake_redis: Any, admin_dispatching: Utilisateur
) -> None:
    response = await _put(
        client, db, admin_dispatching, "causes", _cause("distribution"), _cause("commun"), {"type_reseau": "commun"}
    )
    await _assert_refus_sans_ecriture(response, db, fake_redis, "causes")


async def test_admin_scr_ne_deplace_pas_cause_transport_en_distribution(
    client: AsyncClient, db: AsyncMock, fake_redis: Any, admin_scr: Utilisateur
) -> None:
    response = await _put(
        client, db, admin_scr, "causes", _cause("transport"), _cause("distribution"), {"type_reseau": "distribution"}
    )
    await _assert_refus_sans_ecriture(response, db, fake_redis, "causes")


async def test_admin_scr_ne_deplace_pas_cause_transport_en_commun(
    client: AsyncClient, db: AsyncMock, fake_redis: Any, admin_scr: Utilisateur
) -> None:
    response = await _put(
        client, db, admin_scr, "causes", _cause("transport"), _cause("commun"), {"type_reseau": "commun"}
    )
    await _assert_refus_sans_ecriture(response, db, fake_redis, "causes")


@pytest.mark.parametrize("resource", ["sieges", "signalisations"])
async def test_admin_dispatching_ne_deplace_pas_siege_ou_signalisation_distribution_en_transport(
    client: AsyncClient, db: AsyncMock, fake_redis: Any, admin_dispatching: Utilisateur, resource: str
) -> None:
    fabrique = _FABRIQUES[resource]
    response = await _put(
        client, db, admin_dispatching, resource, fabrique("distribution"), fabrique("transport"),
        {"type_reseau": "transport"},
    )
    await _assert_refus_sans_ecriture(response, db, fake_redis, resource)


async def test_admin_scr_ne_deplace_pas_siege_transport_en_distribution(
    client: AsyncClient, db: AsyncMock, fake_redis: Any, admin_scr: Utilisateur
) -> None:
    response = await _put(
        client, db, admin_scr, "sieges", _siege("transport"), _siege("distribution"), {"type_reseau": "distribution"}
    )
    await _assert_refus_sans_ecriture(response, db, fake_redis, "sieges")


# ---------------------------------------------------------------------------
# Changement de réseau refusé : nouveau réseau hors périmètre (gardes)
# ---------------------------------------------------------------------------


async def test_admin_scr_ne_deplace_pas_cause_commune_en_transport(
    client: AsyncClient, db: AsyncMock, fake_redis: Any, admin_scr: Utilisateur
) -> None:
    response = await _put(
        client, db, admin_scr, "causes", _cause("commun"), _cause("transport"), {"type_reseau": "transport"}
    )
    await _assert_refus_sans_ecriture(response, db, fake_redis, "causes")


async def test_admin_dispatching_ne_deplace_pas_cause_commune_en_distribution(
    client: AsyncClient, db: AsyncMock, fake_redis: Any, admin_dispatching: Utilisateur
) -> None:
    response = await _put(
        client, db, admin_dispatching, "causes", _cause("commun"), _cause("distribution"),
        {"type_reseau": "distribution"},
    )
    await _assert_refus_sans_ecriture(response, db, fake_redis, "causes")


# ---------------------------------------------------------------------------
# Modification sans changement de réseau (gardes)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "payload",
    [
        {"libelle": "Agression (tiers)"},
        {"est_exogene": True},
        {"type_reseau": "distribution", "libelle": "Agression (tiers)"},  # même réseau envoyé
    ],
)
async def test_admin_dispatching_ne_modifie_pas_cause_distribution_sans_changer_le_reseau(
    client: AsyncClient, db: AsyncMock, fake_redis: Any, admin_dispatching: Utilisateur, payload: dict[str, Any]
) -> None:
    response = await _put(
        client, db, admin_dispatching, "causes", _cause("distribution"),
        _cause("distribution", libelle="Agression (tiers)"), payload,
    )
    await _assert_refus_sans_ecriture(response, db, fake_redis, "causes")


async def test_admin_scr_modifie_libelle_cause_distribution(
    client: AsyncClient, db: AsyncMock, fake_redis: Any, admin_scr: Utilisateur
) -> None:
    response = await _put(
        client, db, admin_scr, "causes", _cause("distribution"),
        _cause("distribution", libelle="Agression (tiers)"), {"libelle": "Agression (tiers)"},
    )
    await _assert_modifie(response, db, fake_redis, "causes", None)
    assert "type_reseau" not in _update_params(db)


# ---------------------------------------------------------------------------
# Changements de réseau autorisés (dans les deux périmètres, actuel et nouveau)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("role_fixture", "avant", "apres"),
    [
        ("admin_scr", "distribution", "commun"),
        ("admin_scr", "commun", "distribution"),
        ("admin_dispatching", "commun", "transport"),
        ("admin_dispatching", "transport", "commun"),
    ],
)
async def test_changement_de_reseau_dans_le_perimetre_accepte(
    client: AsyncClient,
    db: AsyncMock,
    fake_redis: Any,
    request: pytest.FixtureRequest,
    role_fixture: str,
    avant: str,
    apres: str,
) -> None:
    user: Utilisateur = request.getfixturevalue(role_fixture)
    response = await _put(client, db, user, "causes", _cause(avant), _cause(apres), {"type_reseau": apres})
    await _assert_modifie(response, db, fake_redis, "causes", apres)


async def test_admin_dispatching_deplace_signalisation_transport_en_commun(
    client: AsyncClient, db: AsyncMock, fake_redis: Any, admin_dispatching: Utilisateur
) -> None:
    response = await _put(
        client, db, admin_dispatching, "signalisations", _signalisation("transport"), _signalisation("commun"),
        {"type_reseau": "commun"},
    )
    await _assert_modifie(response, db, fake_redis, "signalisations", "commun")


# ---------------------------------------------------------------------------
# Élément sans réseau actuel (donnée ancienne)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("role_fixture", "nouveau"),
    [("admin_scr", "distribution"), ("admin_scr", "commun"), ("admin_dispatching", "transport")],
)
async def test_element_sans_reseau_type_envoye_dans_le_perimetre_accepte(
    client: AsyncClient,
    db: AsyncMock,
    fake_redis: Any,
    request: pytest.FixtureRequest,
    role_fixture: str,
    nouveau: str,
) -> None:
    user: Utilisateur = request.getfixturevalue(role_fixture)
    response = await _put(client, db, user, "causes", _cause(None), _cause(nouveau), {"type_reseau": nouveau})
    await _assert_modifie(response, db, fake_redis, "causes", nouveau)


@pytest.mark.parametrize(
    ("role_fixture", "nouveau"),
    [("admin_scr", "transport"), ("admin_dispatching", "distribution")],
)
async def test_element_sans_reseau_type_envoye_hors_perimetre_refuse(
    client: AsyncClient,
    db: AsyncMock,
    fake_redis: Any,
    request: pytest.FixtureRequest,
    role_fixture: str,
    nouveau: str,
) -> None:
    user: Utilisateur = request.getfixturevalue(role_fixture)
    response = await _put(client, db, user, "causes", _cause(None), _cause(nouveau), {"type_reseau": nouveau})
    await _assert_refus_sans_ecriture(response, db, fake_redis, "causes")


async def test_element_sans_reseau_sans_type_envoye_renvoie_422(
    client: AsyncClient, db: AsyncMock, fake_redis: Any, admin_scr: Utilisateur
) -> None:
    response = await _put(
        client, db, admin_scr, "causes", _cause(None), _cause(None, libelle="X"), {"libelle": "X"}
    )
    assert response.status_code == 422, response.text
    erreur = response.json()["detail"]
    assert erreur["status"] == "error"
    assert erreur["data"] is None
    assert "type_reseau obligatoire" in erreur["error"]
    db.execute.assert_not_awaited()
    assert _audits(db) == []
    assert await fake_redis.get("referentiel:causes:version") is None


# ---------------------------------------------------------------------------
# Rôle national et rôles non autorisés
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("resource", "avant", "apres"),
    [
        ("causes", "distribution", "transport"),
        ("causes", "transport", "distribution"),
        ("causes", "commun", "transport"),
        ("sieges", "transport", "distribution"),
        ("signalisations", "distribution", "commun"),
    ],
)
async def test_superadmin_change_le_reseau_partout(
    client: AsyncClient, db: AsyncMock, fake_redis: Any, superadmin: Utilisateur, resource: str, avant: str, apres: str
) -> None:
    fabrique = _FABRIQUES[resource]
    response = await _put(client, db, superadmin, resource, fabrique(avant), fabrique(apres), {"type_reseau": apres})
    await _assert_modifie(response, db, fake_redis, resource, apres)


async def test_superadmin_modifie_cause_sans_reseau_ni_type_envoye(
    client: AsyncClient, db: AsyncMock, fake_redis: Any, superadmin: Utilisateur
) -> None:
    """Superadmin : aucun contrôle de réseau (comportement actuel de ``_ensure_can_write``)."""
    response = await _put(
        client, db, superadmin, "causes", _cause(None), _cause(None, libelle="X"), {"libelle": "X"}
    )
    await _assert_modifie(response, db, fake_redis, "causes", None)


@pytest.mark.parametrize("role_fixture", ["admin_saqs", "bcc_user"])
@pytest.mark.parametrize(("avant", "apres"), [("distribution", "transport"), ("transport", "commun")])
async def test_roles_non_autorises_ne_changent_pas_le_reseau(
    client: AsyncClient,
    db: AsyncMock,
    fake_redis: Any,
    request: pytest.FixtureRequest,
    role_fixture: str,
    avant: str,
    apres: str,
) -> None:
    user: Utilisateur = request.getfixturevalue(role_fixture)
    response = await _put(client, db, user, "causes", _cause(avant), _cause(apres), {"type_reseau": apres})
    await _assert_refus_sans_ecriture(response, db, fake_redis, "causes")


# ---------------------------------------------------------------------------
# Référentiels sans réseau : inchangés (gardes)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("role_fixture", ["admin_scr", "admin_dispatching"])
async def test_nature_modifiable_par_les_deux_admins(
    client: AsyncClient,
    db: AsyncMock,
    fake_redis: Any,
    request: pytest.FixtureRequest,
    role_fixture: str,
) -> None:
    user: Utilisateur = request.getfixturevalue(role_fixture)
    response = await _put(
        client, db, user, "natures", _nature(), _nature(libelle="Coupure programmée"),
        {"libelle": "Coupure programmée"},
    )
    await _assert_modifie(response, db, fake_redis, "natures", None)
    assert "type_reseau" not in _update_params(db)


# ---------------------------------------------------------------------------
# Suppression : le réseau actuel est déjà vérifié (non-régression)
# ---------------------------------------------------------------------------


async def _delete(client: AsyncClient, user: Utilisateur, resource: str, record: Any) -> Any:
    with patch(_USER_GET, return_value=user), patch(_REF_GET, new_callable=AsyncMock, return_value=record):
        return await client.delete(f"/api/v1/referentiel/{resource}/{record.id}", headers=_headers(user))


@pytest.mark.parametrize(
    ("role_fixture", "resource", "type_reseau"),
    [
        ("admin_dispatching", "causes", "distribution"),
        ("admin_scr", "causes", "transport"),
        ("admin_scr", "sieges", "transport"),
        ("admin_saqs", "causes", "distribution"),
    ],
)
async def test_suppression_hors_perimetre_refusee(
    client: AsyncClient,
    db: AsyncMock,
    fake_redis: Any,
    request: pytest.FixtureRequest,
    role_fixture: str,
    resource: str,
    type_reseau: str,
) -> None:
    user: Utilisateur = request.getfixturevalue(role_fixture)
    response = await _delete(client, user, resource, _FABRIQUES[resource](type_reseau))
    await _assert_refus_sans_ecriture(response, db, fake_redis, resource)


@pytest.mark.parametrize(
    ("role_fixture", "type_reseau"),
    [
        ("admin_dispatching", "transport"),
        ("admin_dispatching", "commun"),
        ("admin_scr", "distribution"),
        ("admin_scr", "commun"),
        ("superadmin", "transport"),
    ],
)
async def test_suppression_dans_le_perimetre_acceptee(
    client: AsyncClient,
    db: AsyncMock,
    fake_redis: Any,
    request: pytest.FixtureRequest,
    role_fixture: str,
    type_reseau: str,
) -> None:
    user: Utilisateur = request.getfixturevalue(role_fixture)
    response = await _delete(client, user, "causes", _cause(type_reseau))
    assert response.status_code == 204, response.text
    assert _update_params(db).get("is_active") is False
    assert len([a for a in _audits(db) if a.action == "delete"]) == 1
    assert await fake_redis.get("referentiel:causes:version") == "1"
