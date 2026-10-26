"""Tests unitaires — app/services/auth_service.py.

Couverture :
  login()            — credentials valides, mauvais mdp, compte inactif, première connexion
  refresh()          — token valide, token révoqué, mauvais type, utilisateur désactivé
  logout()           — JTI blacklisté avec TTL correct, refresh JTI supprimé
  get_current_user() — token valide, token expiré, JTI blacklisté, utilisateur introuvable

Règle : pas de DB ni Redis réels — AsyncMock + fakeredis uniquement.
"""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
)
from app.models.utilisateurs import Role, UserRole, Utilisateur
from app.schemas.auth import LoginRequest
from app.services import auth_service

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helpers locaux
# ---------------------------------------------------------------------------


def _make_utilisateur(
    user_id: int = 1,
    login: str = "bcc_user",
    password: str = "MotDePasse123!",
    is_active: bool = True,
    premiere_connexion: bool = False,
    role_nom: str = "BCC",
    scope_service_id: int | None = 1,
) -> Utilisateur:
    """Construit un Utilisateur sans session DB pour les tests unitaires."""
    role = Role()
    role.id = 1
    role.nom = role_nom
    role.description = f"Rôle {role_nom}"
    role.is_active = True
    role.role_permissions = []

    ur = UserRole()
    ur.id = 1
    ur.utilisateur_id = user_id
    ur.role_id = 1
    ur.scope_service_id = scope_service_id
    ur.role = role

    user = Utilisateur()
    user.id = user_id
    user.login = login
    user.password_hash = hash_password(password)
    user.nom = "Diallo"
    user.prenom = "Mamadou"
    user.is_active = is_active
    user.premiere_connexion = premiere_connexion
    user.created_at = datetime(2026, 1, 1, 8, 0, 0)
    user.updated_at = datetime(2026, 1, 1, 8, 0, 0)
    user.user_roles = [ur]
    user.audit_logs = []
    ur.utilisateur = user
    return user


def _login_request(login: str = "bcc_user", password: str = "MotDePasse123!") -> LoginRequest:
    return LoginRequest(login=login, password=password)


# ---------------------------------------------------------------------------
# login() — cas nominal
# ---------------------------------------------------------------------------


async def test_login_returns_dict_with_access_token_on_valid_credentials() -> None:
    """login() avec credentials valides → retourne un dict contenant access_token."""
    user = _make_utilisateur()
    mock_db = AsyncMock()
    mock_redis = AsyncMock()
    mock_redis.setex = AsyncMock()

    with patch(
        "app.repositories.utilisateur_repository.get_by_login",
        return_value=user,
    ):
        result = await auth_service.login(mock_db, mock_redis, _login_request())

    assert "access_token" in result
    assert isinstance(result["access_token"], str)
    assert len(result["access_token"]) > 0


async def test_login_returns_refresh_token_on_valid_credentials() -> None:
    """login() avec credentials valides → dict contient également refresh_token."""
    user = _make_utilisateur()
    mock_db = AsyncMock()
    mock_redis = AsyncMock()
    mock_redis.setex = AsyncMock()

    with patch(
        "app.repositories.utilisateur_repository.get_by_login",
        return_value=user,
    ):
        result = await auth_service.login(mock_db, mock_redis, _login_request())

    assert "refresh_token" in result
    assert isinstance(result["refresh_token"], str)


async def test_login_stores_refresh_jti_in_redis_with_correct_ttl() -> None:
    """login() → refresh JTI stocké dans Redis avec TTL = refresh_token_expire_days * 86400."""
    from app.core.config import settings

    user = _make_utilisateur()
    mock_db = AsyncMock()
    mock_redis = AsyncMock()
    mock_redis.setex = AsyncMock()

    with patch(
        "app.repositories.utilisateur_repository.get_by_login",
        return_value=user,
    ):
        await auth_service.login(mock_db, mock_redis, _login_request())

    mock_redis.setex.assert_called_once()
    call_args = mock_redis.setex.call_args
    # Premier argument : clé Redis (doit contenir 'jwt:refresh:')
    key = call_args[0][0]
    ttl = call_args[0][1]
    assert "jwt:refresh:" in key
    assert ttl == settings.refresh_token_expire_days * 86400


async def test_login_returns_user_object_in_result() -> None:
    """login() → le dict résultat expose l'objet 'user' pour que le router pose le cookie."""
    user = _make_utilisateur()
    mock_db = AsyncMock()
    mock_redis = AsyncMock()
    mock_redis.setex = AsyncMock()

    with patch(
        "app.repositories.utilisateur_repository.get_by_login",
        return_value=user,
    ):
        result = await auth_service.login(mock_db, mock_redis, _login_request())

    assert result["user"] is user


# ---------------------------------------------------------------------------
# login() — 401 — mauvais mot de passe
# ---------------------------------------------------------------------------


async def test_login_raises_401_on_wrong_password() -> None:
    """login() avec mauvais mdp → lève HTTPException 401."""
    user = _make_utilisateur(password="MotDePasse123!")
    mock_db = AsyncMock()
    mock_redis = AsyncMock()

    with patch(
        "app.repositories.utilisateur_repository.get_by_login",
        return_value=user,
    ):
        with pytest.raises(HTTPException) as exc_info:
            await auth_service.login(
                mock_db,
                mock_redis,
                _login_request(password="MauvaisMotDePasse!"),
            )

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail["status"] == "error"
    assert "Identifiants invalides" in exc_info.value.detail["error"]


async def test_login_raises_401_on_unknown_login() -> None:
    """login() avec login inexistant (get_by_login retourne None) → lève HTTPException 401."""
    mock_db = AsyncMock()
    mock_redis = AsyncMock()

    with patch(
        "app.repositories.utilisateur_repository.get_by_login",
        return_value=None,
    ):
        with pytest.raises(HTTPException) as exc_info:
            await auth_service.login(
                mock_db,
                mock_redis,
                _login_request(login="login_inconnu"),
            )

    assert exc_info.value.status_code == 401
    # Même message que mauvais mdp — pas d'user enumeration
    assert "Identifiants invalides" in exc_info.value.detail["error"]


async def test_login_wrong_password_and_unknown_login_return_identical_error() -> None:
    """Mauvais mdp et login inexistant → messages d'erreur identiques (anti user-enumeration)."""
    user = _make_utilisateur()
    mock_db = AsyncMock()
    mock_redis = AsyncMock()

    # Mauvais mot de passe
    with patch(
        "app.repositories.utilisateur_repository.get_by_login",
        return_value=user,
    ):
        with pytest.raises(HTTPException) as exc_wrong_pwd:
            await auth_service.login(
                mock_db, mock_redis, _login_request(password="mauvais")
            )

    # Login inexistant
    with patch(
        "app.repositories.utilisateur_repository.get_by_login",
        return_value=None,
    ):
        with pytest.raises(HTTPException) as exc_unknown:
            await auth_service.login(
                mock_db, mock_redis, _login_request(login="inconnu")
            )

    assert exc_wrong_pwd.value.detail["error"] == exc_unknown.value.detail["error"]


# ---------------------------------------------------------------------------
# login() — 403 — compte inactif
# ---------------------------------------------------------------------------


async def test_login_raises_403_on_inactive_user() -> None:
    """login() avec utilisateur inactif → lève HTTPException 403."""
    user = _make_utilisateur(is_active=False)
    mock_db = AsyncMock()
    mock_redis = AsyncMock()

    with patch(
        "app.repositories.utilisateur_repository.get_by_login",
        return_value=user,
    ):
        with pytest.raises(HTTPException) as exc_info:
            await auth_service.login(mock_db, mock_redis, _login_request())

    assert exc_info.value.status_code == 403
    assert "Compte désactivé" in exc_info.value.detail["error"]


# ---------------------------------------------------------------------------
# login() — 403 — première connexion
# ---------------------------------------------------------------------------


async def test_login_accepts_active_directory_password() -> None:
    """Compte présent dans l'AD : le mot de passe annuaire ouvre la session, sans changement local."""
    user = _make_utilisateur(premiere_connexion=True)
    mock_db = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_redis = AsyncMock()
    mock_redis.setex = AsyncMock()

    with (
        patch("app.repositories.utilisateur_repository.get_by_login", return_value=user),
        patch("app.services.auth_service.ldap_service.verify_user_password", return_value=True),
        patch(
            "app.repositories.utilisateur_repository.update_premiere_connexion",
            new_callable=AsyncMock,
        ) as clear_flag,
    ):
        result = await auth_service.login(
            mock_db, mock_redis, _login_request(password="MotDePasseAnnuaire")
        )

    assert "access_token" in result
    assert user.premiere_connexion is False
    clear_flag.assert_awaited_once()
    mock_db.commit.assert_awaited()


async def test_login_rejects_wrong_active_directory_password() -> None:
    """Compte AD : un mot de passe refusé par l'annuaire ne retombe pas sur le hash local."""
    user = _make_utilisateur()
    mock_db = AsyncMock()
    mock_redis = AsyncMock()

    with (
        patch("app.repositories.utilisateur_repository.get_by_login", return_value=user),
        patch("app.services.auth_service.ldap_service.verify_user_password", return_value=False),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await auth_service.login(mock_db, mock_redis, _login_request())

    assert exc_info.value.status_code == 401


async def test_login_raises_403_force_password_change_on_premiere_connexion() -> None:
    """login() avec premiere_connexion=True → lève HTTPException 403 avec code FORCE_PASSWORD_CHANGE."""
    user = _make_utilisateur(premiere_connexion=True)
    mock_db = AsyncMock()
    mock_redis = AsyncMock()

    with patch(
        "app.repositories.utilisateur_repository.get_by_login",
        return_value=user,
    ):
        with pytest.raises(HTTPException) as exc_info:
            await auth_service.login(mock_db, mock_redis, _login_request())

    assert exc_info.value.status_code == 403
    error = exc_info.value.detail["error"]
    assert isinstance(error, dict)
    assert error["code"] == "FORCE_PASSWORD_CHANGE"


# ---------------------------------------------------------------------------
# logout() — JTI blacklisté dans Redis
# ---------------------------------------------------------------------------


async def test_logout_blacklists_access_jti_in_redis() -> None:
    """logout() → JTI de l'access token ajouté dans Redis avec TTL > 0."""
    mock_redis = AsyncMock()
    mock_redis.setex = AsyncMock()
    mock_redis.delete = AsyncMock()

    # exp dans le futur (token encore valide)
    exp = int((datetime.now(UTC) + timedelta(minutes=25)).timestamp())
    jti = str(uuid.uuid4())

    await auth_service.logout(
        redis=mock_redis,
        access_token_jti=jti,
        access_token_exp=exp,
    )

    mock_redis.setex.assert_called_once()
    call_args = mock_redis.setex.call_args[0]
    key, ttl, value = call_args
    assert f"jwt:blacklist:{jti}" == key
    assert ttl > 0
    assert value == "1"


async def test_logout_does_not_blacklist_already_expired_token() -> None:
    """logout() avec token déjà expiré → setex non appelé (TTL = 0)."""
    mock_redis = AsyncMock()
    mock_redis.setex = AsyncMock()
    mock_redis.delete = AsyncMock()

    # exp dans le passé
    exp = int((datetime.now(UTC) - timedelta(minutes=5)).timestamp())
    jti = str(uuid.uuid4())

    await auth_service.logout(
        redis=mock_redis,
        access_token_jti=jti,
        access_token_exp=exp,
    )

    mock_redis.setex.assert_not_called()


async def test_logout_deletes_refresh_jti_from_redis_when_token_provided() -> None:
    """logout() avec refresh_token → supprime le JTI du refresh dans Redis."""
    mock_redis = AsyncMock()
    mock_redis.setex = AsyncMock()
    mock_redis.delete = AsyncMock()

    user = _make_utilisateur()
    refresh_jti = str(uuid.uuid4())
    refresh_token = create_refresh_token(subject=str(user.id), jti=refresh_jti)
    exp = int((datetime.now(UTC) + timedelta(minutes=25)).timestamp())
    access_jti = str(uuid.uuid4())

    await auth_service.logout(
        redis=mock_redis,
        access_token_jti=access_jti,
        access_token_exp=exp,
        refresh_token=refresh_token,
    )

    mock_redis.delete.assert_called_once_with(f"jwt:refresh:{refresh_jti}")


async def test_logout_ignores_invalid_refresh_token_silently() -> None:
    """logout() avec refresh_token invalide (déjà expiré) → pas d'exception levée."""
    mock_redis = AsyncMock()
    mock_redis.setex = AsyncMock()
    mock_redis.delete = AsyncMock()

    exp = int((datetime.now(UTC) + timedelta(minutes=25)).timestamp())

    # Ne doit pas lever d'exception
    await auth_service.logout(
        redis=mock_redis,
        access_token_jti=str(uuid.uuid4()),
        access_token_exp=exp,
        refresh_token="token_refresh_invalide",
    )


# ---------------------------------------------------------------------------
# get_current_user() — cas nominal
# ---------------------------------------------------------------------------


async def test_get_current_user_returns_user_on_valid_token() -> None:
    """get_current_user() avec token valide et JTI non blacklisté → retourne l'utilisateur."""
    user = _make_utilisateur()
    mock_db = AsyncMock()
    mock_redis = AsyncMock()
    mock_redis.exists = AsyncMock(return_value=0)  # JTI non blacklisté

    jti = str(uuid.uuid4())
    token = create_access_token(
        subject=str(user.id),
        jti=jti,
        extra={"role": "BCC", "service_id": 1},
    )

    with patch(
        "app.repositories.utilisateur_repository.get_by_id",
        return_value=user,
    ):
        result = await auth_service.get_current_user(mock_db, mock_redis, token)

    assert result is user


# ---------------------------------------------------------------------------
# get_current_user() — 401 — JTI blacklisté
# ---------------------------------------------------------------------------


async def test_get_current_user_raises_401_when_jti_is_blacklisted() -> None:
    """get_current_user() avec JTI présent dans Redis blacklist → lève HTTPException 401."""
    user = _make_utilisateur()
    mock_db = AsyncMock()
    mock_redis = AsyncMock()
    mock_redis.exists = AsyncMock(return_value=1)  # JTI blacklisté

    jti = str(uuid.uuid4())
    token = create_access_token(
        subject=str(user.id),
        jti=jti,
        extra={"role": "BCC", "service_id": 1},
    )

    with pytest.raises(HTTPException) as exc_info:
        await auth_service.get_current_user(mock_db, mock_redis, token)

    assert exc_info.value.status_code == 401
    assert "révoquée" in exc_info.value.detail["error"].lower() or "révoqué" in exc_info.value.detail["error"].lower()


# ---------------------------------------------------------------------------
# get_current_user() — 401 — token expiré
# ---------------------------------------------------------------------------


async def test_get_current_user_raises_401_on_expired_token() -> None:
    """get_current_user() avec token JWT expiré → lève HTTPException 401."""
    from jose import jwt as jose_jwt

    from app.core.config import settings
    from app.core.security import ALGORITHM

    jti = str(uuid.uuid4())
    exp = datetime.now(UTC) - timedelta(minutes=5)
    payload = {
        "sub": "1",
        "jti": jti,
        "exp": exp,
        "type": "access",
        "role": "BCC",
        "service_id": 1,
    }
    expired_token = jose_jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)

    mock_db = AsyncMock()
    mock_redis = AsyncMock()

    with pytest.raises(HTTPException) as exc_info:
        await auth_service.get_current_user(mock_db, mock_redis, expired_token)

    assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# get_current_user() — 401 — token malformé
# ---------------------------------------------------------------------------


async def test_get_current_user_raises_401_on_malformed_token() -> None:
    """get_current_user() avec chaîne aléatoire comme token → lève HTTPException 401."""
    mock_db = AsyncMock()
    mock_redis = AsyncMock()

    with pytest.raises(HTTPException) as exc_info:
        await auth_service.get_current_user(
            mock_db, mock_redis, "ceci_nest_pas_un_jwt"
        )

    assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# get_current_user() — 401 — utilisateur introuvable en DB
# ---------------------------------------------------------------------------


async def test_get_current_user_raises_401_when_user_not_found_in_db() -> None:
    """get_current_user() token valide mais utilisateur supprimé de la DB → 401."""
    mock_db = AsyncMock()
    mock_redis = AsyncMock()
    mock_redis.exists = AsyncMock(return_value=0)

    jti = str(uuid.uuid4())
    token = create_access_token(subject="999", jti=jti, extra={})

    with patch(
        "app.repositories.utilisateur_repository.get_by_id",
        return_value=None,
    ):
        with pytest.raises(HTTPException) as exc_info:
            await auth_service.get_current_user(mock_db, mock_redis, token)

    assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# get_current_user() — 403 — utilisateur désactivé
# ---------------------------------------------------------------------------


async def test_get_current_user_raises_403_when_user_is_inactive() -> None:
    """get_current_user() token valide mais utilisateur désactivé → 403."""
    user = _make_utilisateur(is_active=False)
    mock_db = AsyncMock()
    mock_redis = AsyncMock()
    mock_redis.exists = AsyncMock(return_value=0)

    jti = str(uuid.uuid4())
    token = create_access_token(subject=str(user.id), jti=jti, extra={})

    with patch(
        "app.repositories.utilisateur_repository.get_by_id",
        return_value=user,
    ):
        with pytest.raises(HTTPException) as exc_info:
            await auth_service.get_current_user(mock_db, mock_redis, token)

    assert exc_info.value.status_code == 403
    assert "Compte désactivé" in exc_info.value.detail["error"]


# ---------------------------------------------------------------------------
# get_current_user() — 401 — token de type refresh utilisé comme access
# ---------------------------------------------------------------------------


async def test_get_current_user_raises_401_when_refresh_token_used_as_access() -> None:
    """get_current_user() avec un refresh_token (type='refresh') → 401 mauvais type."""
    user = _make_utilisateur()
    mock_db = AsyncMock()
    mock_redis = AsyncMock()
    mock_redis.exists = AsyncMock(return_value=0)

    jti = str(uuid.uuid4())
    # Forger un refresh token à la place d'un access token
    refresh_token = create_refresh_token(subject=str(user.id), jti=jti)

    with pytest.raises(HTTPException) as exc_info:
        await auth_service.get_current_user(mock_db, mock_redis, refresh_token)

    assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# build_me_response() — extraction correcte des champs
# ---------------------------------------------------------------------------


def test_build_me_response_maps_all_fields_correctly() -> None:
    """build_me_response() extrait correctement les champs depuis le modèle ORM."""
    user = _make_utilisateur(
        user_id=42,
        login="admin_scr",
        role_nom="ADMIN_SCR",
        scope_service_id=None,
    )
    user.user_roles[0].scope_service_id = None

    me = auth_service.build_me_response(user)

    assert me.id == 42
    assert me.login == "admin_scr"
    assert me.nom == "Diallo"
    assert me.prenom == "Mamadou"
    assert me.role_label == "ADMIN_SCR"
    assert me.service_id is None
    assert me.is_active is True
    assert me.premiere_connexion is False


def test_build_me_response_returns_none_role_when_no_user_roles() -> None:
    """build_me_response() avec user sans rôle → role_label=None, service_id=None."""
    user = _make_utilisateur()
    user.user_roles = []

    me = auth_service.build_me_response(user)

    assert me.role_label is None
    assert me.service_id is None
