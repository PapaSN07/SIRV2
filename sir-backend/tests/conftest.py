"""Fixtures partagées pour l'ensemble de la suite de tests SIR.

Toutes les fixtures mockent les dépendances externes (DB, Redis).
Aucune connexion réelle à SQL Server ou Redis n'est établie.

Ce module est importé en premier par pytest. Il charge .env.test dans os.environ
AVANT tout import de app.core.config, ce qui permet à pydantic-settings de trouver
les variables sans se connecter à SQL Server ou Redis.
"""

import os
import pathlib

# Charger .env.test avant tout import de l'application
_env_test_path = pathlib.Path(__file__).parent.parent / ".env.test"
if _env_test_path.exists():
    with open(_env_test_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _key, _, _val = _line.partition("=")
                os.environ.setdefault(_key.strip(), _val.strip())

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.security import create_access_token, create_refresh_token, hash_password
from app.models.utilisateurs import Permission, Role, RolePermission, UserRole, Utilisateur


# ---------------------------------------------------------------------------
# Helpers de construction d'objets ORM sans DB
# ---------------------------------------------------------------------------


def _make_role(nom: str = "BCC") -> Role:
    """Construit un Role SQLAlchemy sans session DB."""
    role = Role()
    role.id = 1
    role.nom = nom
    role.description = f"Rôle {nom}"
    role.is_active = True
    role.role_permissions = []
    return role


def _make_user_role(role: Role, scope_service_id: int | None = 1) -> UserRole:
    """Construit un UserRole SQLAlchemy sans session DB."""
    ur = UserRole()
    ur.id = 1
    ur.utilisateur_id = 1
    ur.role_id = role.id
    ur.scope_service_id = scope_service_id
    ur.role = role
    return ur


def _make_utilisateur(
    user_id: int = 1,
    login: str = "bcc_user",
    password: str = "MotDePasse123!",
    is_active: bool = True,
    premiere_connexion: bool = False,
    role_nom: str = "BCC",
    scope_service_id: int | None = 1,
) -> Utilisateur:
    """Construit un Utilisateur SQLAlchemy complet sans session DB."""
    role = _make_role(role_nom)
    user_role = _make_user_role(role, scope_service_id)

    user = Utilisateur()
    user.id = user_id
    user.login = login
    user.password_hash = hash_password(password)
    user.nom = "Diallo"
    user.prenom = "Mamadou"
    user.email = f"{login}@senelec.sn"
    user.telephone = "+221771234567"
    user.is_active = is_active
    user.premiere_connexion = premiere_connexion
    user.created_at = datetime(2026, 1, 1, 8, 0, 0)
    user.updated_at = datetime(2026, 1, 1, 8, 0, 0)
    user.user_roles = [user_role]
    user.audit_logs = []
    user_role.utilisateur = user
    return user


# ---------------------------------------------------------------------------
# Fixtures utilisateur
# ---------------------------------------------------------------------------


@pytest.fixture
def utilisateur_actif() -> Utilisateur:
    """Utilisateur actif, première connexion déjà effectuée, rôle BCC service 1."""
    return _make_utilisateur(
        user_id=1,
        login="bcc_user",
        password="MotDePasse123!",
        is_active=True,
        premiere_connexion=False,
        role_nom="BCC",
        scope_service_id=1,
    )


@pytest.fixture
def utilisateur_inactif() -> Utilisateur:
    """Utilisateur désactivé — login doit renvoyer 403."""
    return _make_utilisateur(
        user_id=2,
        login="bcc_inactif",
        password="MotDePasse123!",
        is_active=False,
        premiere_connexion=False,
    )


@pytest.fixture
def utilisateur_premiere_connexion() -> Utilisateur:
    """Utilisateur actif mais premiere_connexion=True — login doit renvoyer 403 FORCE_PASSWORD_CHANGE."""
    return _make_utilisateur(
        user_id=3,
        login="bcc_new",
        password="MotDePasse123!",
        is_active=True,
        premiere_connexion=True,
    )


# ---------------------------------------------------------------------------
# Fixtures tokens JWT
# ---------------------------------------------------------------------------


@pytest.fixture
def access_token_valide(utilisateur_actif: Utilisateur) -> str:
    """Access token JWT valide pour utilisateur_actif."""
    jti = str(uuid.uuid4())
    return create_access_token(
        subject=str(utilisateur_actif.id),
        jti=jti,
        extra={"role": "BCC", "service_id": 1},
    )


@pytest.fixture
def access_token_avec_jti(utilisateur_actif: Utilisateur) -> tuple[str, str]:
    """Retourne (access_token, jti) pour les tests de blacklist."""
    jti = str(uuid.uuid4())
    token = create_access_token(
        subject=str(utilisateur_actif.id),
        jti=jti,
        extra={"role": "BCC", "service_id": 1},
    )
    return token, jti


@pytest.fixture
def refresh_token_valide(utilisateur_actif: Utilisateur) -> str:
    """Refresh token JWT valide pour utilisateur_actif."""
    jti = str(uuid.uuid4())
    return create_refresh_token(
        subject=str(utilisateur_actif.id),
        jti=jti,
    )


@pytest.fixture
def access_token_expire() -> str:
    """Access token JWT déjà expiré (exp dans le passé)."""
    from jose import jwt as jose_jwt

    from app.core.config import settings
    from app.core.security import ALGORITHM

    jti = str(uuid.uuid4())
    expire = datetime.now(UTC) - timedelta(minutes=5)
    payload = {
        "sub": "1",
        "jti": jti,
        "exp": expire,
        "type": "access",
        "role": "BCC",
        "service_id": 1,
    }
    return jose_jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


# ---------------------------------------------------------------------------
# Fixtures Redis (fakeredis)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def fake_redis():
    """Instance fakeredis en mémoire — remplace Redis réel dans les tests."""
    try:
        import fakeredis.aioredis as fakeredis_async  # type: ignore[import]

        redis = fakeredis_async.FakeRedis(decode_responses=True)
        yield redis
        await redis.aclose()
    except ImportError:
        # Fallback : mock complet si fakeredis non installé
        pytest.skip("fakeredis non installé — pip install fakeredis")


# ---------------------------------------------------------------------------
# Fixtures DB (AsyncMock — jamais de vraie connexion SQL Server)
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_db() -> AsyncMock:
    """Session SQLAlchemy mockée. Les repositories doivent être patchés séparément."""
    session = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.flush = AsyncMock()
    return session


# ---------------------------------------------------------------------------
# App FastAPI de test avec overrides de dépendances
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def client(mock_db: AsyncMock, fake_redis: Any) -> AsyncClient:
    """Client httpx AsyncClient pointant sur l'app FastAPI avec DB et Redis mockés.

    Les dépendances get_db et get_redis sont remplacées par des mocks
    pour éviter toute connexion réelle à SQL Server ou Redis.
    """
    from app.core.database import get_db
    from app.core.redis import get_redis
    from app.main import app

    async def _override_get_db():
        yield mock_db

    async def _override_get_redis():
        return fake_redis

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_redis] = _override_get_redis

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()
