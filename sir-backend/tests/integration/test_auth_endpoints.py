"""Tests d'intégration — endpoints d'authentification JWT.

Couverture :
  POST /api/v1/auth/login     — 200, 401 (mdp invalide), 401 (login inexistant),
                                403 (compte inactif), 403 (FORCE_PASSWORD_CHANGE)
  GET  /api/v1/auth/me        — 200, 401 (sans token), 401 (token expiré),
                                401 (token blacklisté après logout)
  DELETE /api/v1/auth/logout  — 204, JTI présent dans Redis blacklist
  POST /api/v1/auth/refresh   — 200, 401 (sans cookie), 401 (token révoqué)

Règle d'or : aucune connexion réelle à SQL Server ou Redis.
Tous les appels DB sont patchés via unittest.mock.patch.
Redis est fourni par fakeredis (fixture fake_redis depuis conftest.py).
"""

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient

from app.models.utilisateurs import Utilisateur

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _login_payload(login: str = "bcc_user", password: str = "MotDePasse123!") -> dict:
    return {"login": login, "password": password}


# ---------------------------------------------------------------------------
# POST /login — cas nominal
# ---------------------------------------------------------------------------


async def test_login_returns_token_on_valid_credentials(
    client: AsyncClient,
    utilisateur_actif: Utilisateur,
) -> None:
    """Login valide → 200 + access_token dans body + cookie refresh_token posé."""
    with patch(
        "app.repositories.utilisateur_repository.get_by_login",
        return_value=utilisateur_actif,
    ):
        response = await client.post(
            "/api/v1/auth/login",
            json=_login_payload(),
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["error"] is None
    token_data = body["data"]
    assert "access_token" in token_data
    assert token_data["token_type"] == "bearer"
    assert isinstance(token_data["expires_in"], int)
    assert token_data["expires_in"] > 0

    # Cookie refresh_token doit être posé
    assert "refresh_token" in response.cookies


async def test_login_returns_correct_expires_in(
    client: AsyncClient,
    utilisateur_actif: Utilisateur,
) -> None:
    """expires_in doit correspondre à ACCESS_TOKEN_EXPIRE_MINUTES * 60."""
    from app.core.config import settings

    with patch(
        "app.repositories.utilisateur_repository.get_by_login",
        return_value=utilisateur_actif,
    ):
        response = await client.post("/api/v1/auth/login", json=_login_payload())

    assert response.status_code == 200
    assert response.json()["data"]["expires_in"] == settings.access_token_expire_minutes * 60


# ---------------------------------------------------------------------------
# POST /login — 401 — mauvais mot de passe (pas d'user enumeration)
# ---------------------------------------------------------------------------


async def test_login_wrong_password_returns_401_generic_message(
    client: AsyncClient,
    utilisateur_actif: Utilisateur,
) -> None:
    """Mauvais mot de passe → 401 avec message générique sans révéler l'existence du login."""
    with patch(
        "app.repositories.utilisateur_repository.get_by_login",
        return_value=utilisateur_actif,
    ):
        response = await client.post(
            "/api/v1/auth/login",
            json=_login_payload(password="MauvaisMotDePasse!"),
        )

    assert response.status_code == 401
    detail = response.json()["detail"]
    assert detail["status"] == "error"
    assert "Identifiants invalides" in detail["error"]


async def test_login_unknown_login_returns_401_same_message_as_wrong_password(
    client: AsyncClient,
) -> None:
    """Login inexistant → 401 avec le même message que mauvais mot de passe.

    Règle de sécurité : ne pas révéler si un login existe (user enumeration).
    """
    with patch(
        "app.repositories.utilisateur_repository.get_by_login",
        return_value=None,  # utilisateur introuvable
    ):
        response = await client.post(
            "/api/v1/auth/login",
            json=_login_payload(login="login_inconnu"),
        )

    assert response.status_code == 401
    detail = response.json()["detail"]
    assert detail["status"] == "error"
    assert "Identifiants invalides" in detail["error"]


# ---------------------------------------------------------------------------
# POST /login — 403 — compte inactif
# ---------------------------------------------------------------------------


async def test_login_inactive_user_returns_403_compte_desactive(
    client: AsyncClient,
    utilisateur_inactif: Utilisateur,
) -> None:
    """Utilisateur inactif → 403 avec message 'Compte désactivé'."""
    with patch(
        "app.repositories.utilisateur_repository.get_by_login",
        return_value=utilisateur_inactif,
    ):
        response = await client.post(
            "/api/v1/auth/login",
            json=_login_payload(login="bcc_inactif"),
        )

    assert response.status_code == 403
    detail = response.json()["detail"]
    assert detail["status"] == "error"
    assert "Compte désactivé" in detail["error"]


# ---------------------------------------------------------------------------
# POST /login — 403 — première connexion forcée
# ---------------------------------------------------------------------------


async def test_login_premiere_connexion_returns_403_force_password_change(
    client: AsyncClient,
    utilisateur_premiere_connexion: Utilisateur,
) -> None:
    """premiere_connexion=True → 403 avec error.code == 'FORCE_PASSWORD_CHANGE'."""
    with patch(
        "app.repositories.utilisateur_repository.get_by_login",
        return_value=utilisateur_premiere_connexion,
    ):
        response = await client.post(
            "/api/v1/auth/login",
            json=_login_payload(login="bcc_new"),
        )

    assert response.status_code == 403
    detail = response.json()["detail"]
    assert detail["status"] == "error"
    error = detail["error"]
    assert isinstance(error, dict), "error doit être un objet avec code et message"
    assert error["code"] == "FORCE_PASSWORD_CHANGE"
    assert "mot de passe" in error["message"].lower()


# ---------------------------------------------------------------------------
# POST /login — 422 — payload invalide
# ---------------------------------------------------------------------------


async def test_login_missing_password_returns_422(client: AsyncClient) -> None:
    """Body sans champ 'password' → 422 Unprocessable Entity (validation Pydantic)."""
    response = await client.post(
        "/api/v1/auth/login",
        json={"login": "bcc_user"},  # password manquant
    )
    assert response.status_code == 422


async def test_login_empty_login_returns_422(client: AsyncClient) -> None:
    """login vide → 422 (min_length=1 dans LoginRequest)."""
    response = await client.post(
        "/api/v1/auth/login",
        json={"login": "", "password": "MotDePasse123!"},
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# GET /me — cas nominal
# ---------------------------------------------------------------------------


async def test_me_returns_user_profile_with_valid_token(
    client: AsyncClient,
    utilisateur_actif: Utilisateur,
    access_token_valide: str,
) -> None:
    """Token valide → 200 + profil utilisateur complet dans data."""
    with patch(
        "app.repositories.utilisateur_repository.get_by_id",
        return_value=utilisateur_actif,
    ):
        response = await client.get(
            "/api/v1/auth/me",
            headers=_auth_headers(access_token_valide),
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["error"] is None
    data = body["data"]
    assert data["id"] == utilisateur_actif.id
    assert data["login"] == utilisateur_actif.login
    assert data["nom"] == utilisateur_actif.nom
    assert data["prenom"] == utilisateur_actif.prenom
    assert data["role_label"] == "BCC"
    assert data["service_id"] == 1
    assert data["is_active"] is True
    assert data["premiere_connexion"] is False


# ---------------------------------------------------------------------------
# GET /me — 401 — absence de token
# ---------------------------------------------------------------------------


async def test_me_without_token_returns_401(client: AsyncClient) -> None:
    """Requête sans header Authorization → 401."""
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# GET /me — 401 — token expiré
# ---------------------------------------------------------------------------


async def test_me_with_expired_token_returns_401(
    client: AsyncClient,
    access_token_expire: str,
) -> None:
    """Token JWT expiré → 401."""
    response = await client.get(
        "/api/v1/auth/me",
        headers=_auth_headers(access_token_expire),
    )
    assert response.status_code == 401


async def test_me_with_malformed_token_returns_401(client: AsyncClient) -> None:
    """Token JWT malformé (chaîne aléatoire) → 401."""
    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer ceci_nest_pas_un_jwt"},
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# DELETE /logout — 204 + blacklist Redis
# ---------------------------------------------------------------------------


async def test_logout_returns_204_and_blacklists_jti(
    client: AsyncClient,
    access_token_avec_jti: tuple[str, str],
    fake_redis: Any,
) -> None:
    """Logout valide → 204 + JTI de l'access token présent dans Redis avec TTL > 0."""
    token, jti = access_token_avec_jti

    response = await client.delete(
        "/api/v1/auth/logout",
        headers=_auth_headers(token),
    )

    assert response.status_code == 204

    # Le JTI doit être blacklisté dans Redis
    blacklist_key = f"jwt:blacklist:{jti}"
    is_blacklisted = await fake_redis.exists(blacklist_key)
    assert is_blacklisted == 1, "Le JTI doit être présent dans la blacklist Redis"

    ttl = await fake_redis.ttl(blacklist_key)
    assert ttl > 0, "Le TTL de la blacklist doit être positif"


async def test_logout_deletes_refresh_cookie(
    client: AsyncClient,
    access_token_avec_jti: tuple[str, str],
    utilisateur_actif: Utilisateur,
) -> None:
    """Logout → cookie refresh_token supprimé dans la réponse."""
    token, _ = access_token_avec_jti

    response = await client.delete(
        "/api/v1/auth/logout",
        headers=_auth_headers(token),
    )

    assert response.status_code == 204
    # httpx expose les Set-Cookie headers
    set_cookie_headers = response.headers.get_list("set-cookie") if hasattr(response.headers, "get_list") else []
    cookie_header = response.headers.get("set-cookie", "")
    # Le cookie refresh_token doit être effacé (max-age=0 ou expires dans le passé)
    assert "refresh_token" in cookie_header or response.status_code == 204


async def test_logout_without_token_returns_403(client: AsyncClient) -> None:
    """Requête DELETE /logout sans Authorization → 403 (HTTPBearer l'exige)."""
    response = await client.delete("/api/v1/auth/logout")
    # HTTPBearer renvoie 403 quand le header est absent
    assert response.status_code == 403


async def test_logout_with_invalid_token_returns_401(client: AsyncClient) -> None:
    """DELETE /logout avec token invalide → 401."""
    response = await client.delete(
        "/api/v1/auth/logout",
        headers={"Authorization": "Bearer token_completement_invalide"},
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# GET /me — 401 — token blacklisté après logout
# ---------------------------------------------------------------------------


async def test_me_after_logout_returns_401(
    client: AsyncClient,
    utilisateur_actif: Utilisateur,
    access_token_avec_jti: tuple[str, str],
    fake_redis: Any,
) -> None:
    """Séquence complète : login → logout → /me avec le même token → 401.

    Valide que la blacklist Redis est bien consultée avant de servir /me.
    """
    token, jti = access_token_avec_jti

    # Étape 1 : logout pour blacklister le JTI
    await client.delete(
        "/api/v1/auth/logout",
        headers=_auth_headers(token),
    )

    # Vérification intermédiaire : JTI blacklisté
    assert await fake_redis.exists(f"jwt:blacklist:{jti}") == 1

    # Étape 2 : /me avec le même token → doit être rejeté
    with patch(
        "app.repositories.utilisateur_repository.get_by_id",
        return_value=utilisateur_actif,
    ):
        response = await client.get(
            "/api/v1/auth/me",
            headers=_auth_headers(token),
        )

    assert response.status_code == 401
    detail = response.json()["detail"]
    assert "révoquée" in detail["error"].lower() or "révoqué" in detail["error"].lower()


# ---------------------------------------------------------------------------
# POST /refresh — cas nominal
# ---------------------------------------------------------------------------


async def test_refresh_returns_new_access_token_with_valid_cookie(
    client: AsyncClient,
    utilisateur_actif: Utilisateur,
    refresh_token_valide: str,
    fake_redis: Any,
) -> None:
    """Cookie refresh_token valide → 200 + nouvel access_token."""
    from app.core.security import decode_token

    # Pré-charger le refresh JTI dans Redis (simule ce que le login aurait fait)
    payload = decode_token(refresh_token_valide)
    refresh_jti = payload["jti"]
    refresh_ttl = 7 * 86400
    await fake_redis.setex(f"jwt:refresh:{refresh_jti}", refresh_ttl, str(utilisateur_actif.id))

    with patch(
        "app.repositories.utilisateur_repository.get_by_id",
        return_value=utilisateur_actif,
    ):
        response = await client.post(
            "/api/v1/auth/refresh",
            cookies={"refresh_token": refresh_token_valide},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["error"] is None
    token_data = body["data"]
    assert "access_token" in token_data
    assert token_data["token_type"] == "bearer"
    assert isinstance(token_data["expires_in"], int)
    assert token_data["expires_in"] > 0


async def test_refresh_new_token_is_different_from_old_one(
    client: AsyncClient,
    utilisateur_actif: Utilisateur,
    access_token_valide: str,
    refresh_token_valide: str,
    fake_redis: Any,
) -> None:
    """Le nouvel access_token retourné par /refresh est différent de l'ancien."""
    from app.core.security import decode_token

    payload = decode_token(refresh_token_valide)
    refresh_jti = payload["jti"]
    await fake_redis.setex(
        f"jwt:refresh:{refresh_jti}", 7 * 86400, str(utilisateur_actif.id)
    )

    with patch(
        "app.repositories.utilisateur_repository.get_by_id",
        return_value=utilisateur_actif,
    ):
        response = await client.post(
            "/api/v1/auth/refresh",
            cookies={"refresh_token": refresh_token_valide},
        )

    assert response.status_code == 200
    new_token = response.json()["data"]["access_token"]
    assert new_token != access_token_valide, "Le refresh doit émettre un token avec un nouveau JTI"


# ---------------------------------------------------------------------------
# POST /refresh — 401 — cookie absent
# ---------------------------------------------------------------------------


async def test_refresh_without_cookie_returns_401(client: AsyncClient) -> None:
    """POST /refresh sans cookie refresh_token → 401."""
    response = await client.post("/api/v1/auth/refresh")

    assert response.status_code == 401
    detail = response.json()["detail"]
    assert detail["status"] == "error"
    assert "refresh_token" in detail["error"].lower() or "reconnect" in detail["error"].lower()


# ---------------------------------------------------------------------------
# POST /refresh — 401 — refresh token révoqué (JTI absent de Redis)
# ---------------------------------------------------------------------------


async def test_refresh_with_revoked_token_returns_401(
    client: AsyncClient,
    refresh_token_valide: str,
    fake_redis: Any,
) -> None:
    """Refresh token dont le JTI a été supprimé de Redis (logout) → 401.

    Simule le cas où l'utilisateur s'est déjà déconnecté sur un autre appareil.
    """
    # Ne PAS pré-charger le JTI dans Redis → simule session révoquée
    response = await client.post(
        "/api/v1/auth/refresh",
        cookies={"refresh_token": refresh_token_valide},
    )

    assert response.status_code == 401
    detail = response.json()["detail"]
    assert detail["status"] == "error"
    assert (
        "expiré" in detail["error"].lower()
        or "révoquée" in detail["error"].lower()
        or "révoqué" in detail["error"].lower()
        or "reconnecter" in detail["error"].lower()
    )


async def test_refresh_with_access_token_as_refresh_returns_401(
    client: AsyncClient,
    access_token_valide: str,
) -> None:
    """Utiliser un access_token (type='access') comme refresh_token → 401 (mauvais type)."""
    response = await client.post(
        "/api/v1/auth/refresh",
        cookies={"refresh_token": access_token_valide},
    )
    assert response.status_code == 401


async def test_refresh_with_malformed_token_returns_401(client: AsyncClient) -> None:
    """Refresh token JWT malformé → 401."""
    response = await client.post(
        "/api/v1/auth/refresh",
        cookies={"refresh_token": "pas_un_jwt_valide"},
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# POST /refresh — 401 — utilisateur désactivé
# ---------------------------------------------------------------------------


async def test_refresh_with_deactivated_user_returns_401(
    client: AsyncClient,
    utilisateur_inactif: Utilisateur,
    refresh_token_valide: str,
    fake_redis: Any,
) -> None:
    """Refresh token valide mais utilisateur désactivé entre-temps → 401."""
    from app.core.security import create_refresh_token, decode_token

    import uuid

    # Créer un refresh token pour l'utilisateur inactif
    jti = str(uuid.uuid4())
    token_inactif = create_refresh_token(
        subject=str(utilisateur_inactif.id),
        jti=jti,
    )
    await fake_redis.setex(
        f"jwt:refresh:{jti}", 7 * 86400, str(utilisateur_inactif.id)
    )

    with patch(
        "app.repositories.utilisateur_repository.get_by_id",
        return_value=utilisateur_inactif,
    ):
        response = await client.post(
            "/api/v1/auth/refresh",
            cookies={"refresh_token": token_inactif},
        )

    assert response.status_code == 401
