"""Droits admin et rôles désactivés détenus par l'admin lui-même (suite de test_admin_droits_suivis.py).

Depuis que le compte connecté n'est plus chargé qu'avec ses rôles actifs
(`utilisateur_repository`), un rôle désactivé que l'admin détient n'apparaît plus dans
`current_user.user_roles`.

1. Matrice (`admin_advanced_service.update_role`, PUT /api/v1/admin/roles/{role_id}) : un admin non
   superadmin ne modifie pas les droits d'un rôle qu'il détient, MÊME désactivé. La détention se lit
   en base (ligne user_roles), pas dans `current_user`. Test sur SQLite réel.
2. Modification de son propre compte (PUT /api/v1/admin/utilisateurs/{id}) par un admin qui détient
   un rôle créé désactivé : si l'ensemble (role_id, scope_service_id) demandé, une fois retirés les
   rôles désactivés qu'il détient déjà, égale l'ensemble de ses rôles actifs, le profil est modifié
   (200) et les rôles ne sont pas remplacés (rôle désactivé conservé). Tout autre changement est
   accepté depuis la décision du 26/11/2026 (un admin fait tout sur son propre compte ; remplace la
   règle du 26/11/2026 « un admin ne change ni ses propres rôles ni son mot de passe par
   l'administration ») : test_admin_ne_s_ajoute_pas_un_role_meme_avec_un_role_desactive (403) →
   test_admin_s_ajoute_un_role_meme_avec_un_role_desactive (200, rôles écrits, rôle désactivé
   détenu conservé, audit).
"""

import uuid
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.security import create_access_token
from app.models.utilisateurs import Permission, Role, RolePermission, UserRole, Utilisateur
from app.repositories import utilisateur_repository
from app.schemas.admin import RoleUpdate
from app.services import admin_advanced_service

pytestmark = pytest.mark.asyncio

URL = "/api/v1/admin/utilisateurs"

# ===========================================================================
# 1. Matrice : rôle détenu désactivé (SQLite réel)
# ===========================================================================

_DDL = (
    "CREATE TABLE utilisateurs (id INTEGER PRIMARY KEY, login TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL, "
    "nom TEXT NOT NULL, prenom TEXT NOT NULL, email TEXT, matricule TEXT, telephone TEXT, "
    "is_active BOOLEAN NOT NULL DEFAULT 1, premiere_connexion BOOLEAN NOT NULL DEFAULT 0, "
    "direction_source_id INT, created_at DATETIME DEFAULT CURRENT_TIMESTAMP, "
    "updated_at DATETIME DEFAULT CURRENT_TIMESTAMP)",
    "CREATE TABLE roles (id INTEGER PRIMARY KEY, nom TEXT NOT NULL UNIQUE, description TEXT, "
    "is_active BOOLEAN NOT NULL DEFAULT 1)",
    "CREATE TABLE permissions (id INTEGER PRIMARY KEY, ressource TEXT NOT NULL, action TEXT NOT NULL, "
    "description TEXT, UNIQUE (ressource, action))",
    "CREATE TABLE role_permissions (id INTEGER PRIMARY KEY, role_id INT NOT NULL, permission_id INT NOT NULL, "
    "UNIQUE (role_id, permission_id))",
    "CREATE TABLE user_roles (id INTEGER PRIMARY KEY, utilisateur_id INT NOT NULL, role_id INT NOT NULL, "
    "scope_service_id INT, UNIQUE (utilisateur_id, role_id))",
    "INSERT INTO roles (id, nom, description, is_active) VALUES "
    "(1, 'ADMIN_SCR', 'Admin SCR', 1), (60, 'CREE_DETENU_DESACTIVE', 'Rôle créé désactivé détenu', 0), "
    "(61, 'CREE_LIBRE_DESACTIVE', 'Rôle créé désactivé non détenu', 0)",
    "INSERT INTO permissions (id, ressource, action) VALUES "
    "(1, 'admin_roles', 'read'), (2, 'admin_roles', 'update'), (3, 'rapports', 'read'), (4, 'indicateurs', 'read')",
    "INSERT INTO role_permissions (id, role_id, permission_id) VALUES (1, 1, 1), (2, 1, 2), (3, 60, 3), (4, 61, 3)",
    "INSERT INTO utilisateurs (id, login, password_hash, nom, prenom, is_active, premiere_connexion) "
    "VALUES (1, 'admin_scr', 'x', 'Admin', 'Scr', 1, 0)",
    "INSERT INTO user_roles (id, utilisateur_id, role_id, scope_service_id) VALUES (1, 1, 1, NULL), (2, 1, 60, NULL)",
)

ID_ADMIN_SCR, ID_ROLE_DETENU, ID_ROLE_LIBRE = 1, 60, 61
PERM_RAPPORTS, PERM_INDICATEURS = 3, 4


@pytest.fixture
async def db():
    moteur = create_async_engine("sqlite+aiosqlite://", execution_options={"schema_translate_map": {"dbo": None}})
    async with moteur.begin() as conn:
        for ddl in _DDL:
            await conn.exec_driver_sql(ddl)
    async with AsyncSession(moteur) as session:
        yield session
    await moteur.dispose()


async def _droits_en_base(db: AsyncSession, role_id: int) -> list[int]:
    rows = await db.execute(
        text("SELECT permission_id FROM role_permissions WHERE role_id = :r ORDER BY permission_id"), {"r": role_id}
    )
    return [pid for (pid,) in rows.all()]


async def _admin_connecte(db: AsyncSession) -> Utilisateur:
    """Compte connecté tel que chargé par get_current_user (rôles actifs seulement)."""
    compte = await utilisateur_repository.get_by_id(db, ID_ADMIN_SCR)
    assert compte is not None
    return compte


async def test_montage_le_compte_connecte_ne_porte_pas_le_role_desactive(db: AsyncSession) -> None:
    """Prérequis du scénario : le rôle désactivé détenu n'est pas dans current_user."""
    compte = await _admin_connecte(db)
    assert [ur.role.nom for ur in compte.user_roles] == ["ADMIN_SCR"]


async def test_admin_ne_modifie_pas_les_droits_d_un_role_desactive_qu_il_detient(db: AsyncSession) -> None:
    compte = await _admin_connecte(db)
    with patch("app.services.admin_advanced_service.log_audit", new_callable=AsyncMock) as audit:
        with pytest.raises(HTTPException) as exc:
            await admin_advanced_service.update_role(
                db, compte, ID_ROLE_DETENU, RoleUpdate(permission_ids=[PERM_RAPPORTS, PERM_INDICATEURS])
            )
    assert exc.value.status_code == 403
    assert exc.value.detail["status"] == "error" and exc.value.detail["data"] is None
    assert isinstance(exc.value.detail["error"], str) and exc.value.detail["error"].strip()
    audit.assert_not_awaited()
    assert await _droits_en_base(db, ID_ROLE_DETENU) == [PERM_RAPPORTS]


async def test_admin_ne_reactive_pas_un_role_desactive_qu_il_detient(db: AsyncSession) -> None:
    """Réactiver un rôle détenu lui redonnerait ses droits : même refus."""
    compte = await _admin_connecte(db)
    with patch("app.services.admin_advanced_service.log_audit", new_callable=AsyncMock) as audit:
        with pytest.raises(HTTPException) as exc:
            await admin_advanced_service.update_role(db, compte, ID_ROLE_DETENU, RoleUpdate(is_active=True))
    assert exc.value.status_code == 403
    audit.assert_not_awaited()
    actif = (await db.execute(text("SELECT is_active FROM roles WHERE id = :r"), {"r": ID_ROLE_DETENU})).scalar_one()
    assert not actif


async def test_admin_modifie_un_role_desactive_qu_il_ne_detient_pas(db: AsyncSession) -> None:
    """Garde : rôle désactivé non détenu → modification acceptée."""
    compte = await _admin_connecte(db)
    with patch("app.services.admin_advanced_service.log_audit", new_callable=AsyncMock) as audit:
        reponse = await admin_advanced_service.update_role(
            db, compte, ID_ROLE_LIBRE, RoleUpdate(permission_ids=[PERM_RAPPORTS, PERM_INDICATEURS])
        )
    assert {p.id for p in reponse.permissions} == {PERM_RAPPORTS, PERM_INDICATEURS}
    audit.assert_awaited_once()
    assert await _droits_en_base(db, ID_ROLE_LIBRE) == [PERM_RAPPORTS, PERM_INDICATEURS]


async def test_admin_ne_modifie_pas_un_role_actif_qu_il_detient(db: AsyncSession) -> None:
    """Garde : rôle actif détenu → 403 (déjà le cas)."""
    compte = await _admin_connecte(db)
    with patch("app.services.admin_advanced_service.log_audit", new_callable=AsyncMock) as audit:
        with pytest.raises(HTTPException) as exc:
            await admin_advanced_service.update_role(
                db, compte, ID_ADMIN_SCR, RoleUpdate(permission_ids=[1, 2, PERM_INDICATEURS])
            )
    assert exc.value.status_code == 403
    audit.assert_not_awaited()
    assert await _droits_en_base(db, ID_ADMIN_SCR) == [1, 2]


# ===========================================================================
# 2. Son propre compte avec un rôle créé désactivé (HTTP, objets en mémoire)
# ===========================================================================

_DROITS_ADMIN = [("admin_utilisateurs", "read"), ("admin_utilisateurs", "create"), ("admin_utilisateurs", "update")]

# nom → (id, actif, droits)
CATALOGUE: dict[str, tuple[int, bool, list[tuple[str, str]]]] = {
    "ADMIN_SCR": (1, True, _DROITS_ADMIN),
    "CREE_SANS_DROIT": (50, True, []),
    "CREE_DESACTIVE": (60, False, [("rapports", "read")]),
}


def _role(nom: str) -> Role:
    rid, actif, droits = CATALOGUE[nom]
    role = Role()
    role.id = rid
    role.nom = nom
    role.description = f"Rôle {nom}"
    role.is_active = actif
    rps: list[RolePermission] = []
    for i, (ressource, action) in enumerate(droits, start=1):
        perm = Permission()
        perm.id = rid * 10 + i
        perm.ressource = ressource
        perm.action = action
        perm.description = f"{ressource}:{action}"
        rp = RolePermission()
        rp.id = rid * 100 + i
        rp.role_id = rid
        rp.permission_id = perm.id
        rp.role = role
        rp.permission = perm
        rps.append(rp)
    role.role_permissions = rps
    return role


def _compte(roles: list[str]) -> Utilisateur:
    user = Utilisateur()
    user.id = 1
    user.login = "admin_scr"
    user.password_hash = "hash-non-utilise"
    user.nom = "Nom"
    user.prenom = "Prenom"
    user.email = "admin_scr@senelec.sn"
    user.telephone = None
    user.matricule = None
    user.is_active = True
    user.premiere_connexion = False
    user.audit_logs = []
    user_roles: list[UserRole] = []
    for i, nom in enumerate(roles, start=1):
        ur = UserRole()
        ur.id = 10 + i
        ur.utilisateur_id = user.id
        ur.role_id = CATALOGUE[nom][0]
        ur.scope_service_id = None
        ur.role = _role(nom)
        ur.utilisateur = user
        user_roles.append(ur)
    user.user_roles = user_roles
    return user


def _token(user: Utilisateur) -> dict[str, str]:
    token = create_access_token(subject=str(user.id), jti=str(uuid.uuid4()), extra={"role": "ADMIN_SCR"})
    return {"Authorization": f"Bearer {token}"}


def _attribution(nom: str) -> dict:
    return {"role_id": CATALOGUE[nom][0], "scope_service_id": None}


@dataclass
class Ecritures:
    update_profile: AsyncMock
    replace_roles: AsyncMock
    log_audit: AsyncMock


@contextmanager
def _environnement() -> Iterator[Ecritures]:
    """Compte connecté = rôles actifs seulement ; cible vue par l'administration = tous ses rôles."""
    connecte = _compte(["ADMIN_SCR"])
    cible = _compte(["ADMIN_SCR", "CREE_DESACTIVE"])

    async def _get_role(db, role_id):  # noqa: ANN001, ANN202
        for nom, (rid, _, _) in CATALOGUE.items():
            if rid == role_id:
                return _role(nom)
        return None

    async def _update_profile(db, user, **kwargs):  # noqa: ANN001, ANN003, ANN202
        return user

    with ExitStack() as pile:
        pile.enter_context(
            patch("app.repositories.utilisateur_repository.get_by_id", new_callable=AsyncMock, return_value=connecte)
        )
        pile.enter_context(
            patch("app.repositories.admin_utilisateur_repository.get_by_id", new_callable=AsyncMock, return_value=cible)
        )
        pile.enter_context(
            patch("app.repositories.admin_utilisateur_repository.get_role_by_id", side_effect=_get_role)
        )
        yield Ecritures(
            update_profile=pile.enter_context(
                patch(
                    "app.repositories.admin_utilisateur_repository.update_profile",
                    new_callable=AsyncMock,
                    side_effect=_update_profile,
                )
            ),
            replace_roles=pile.enter_context(
                patch("app.repositories.admin_utilisateur_repository.replace_roles", new_callable=AsyncMock)
            ),
            log_audit=pile.enter_context(
                patch("app.services.admin_utilisateur_service.log_audit", new_callable=AsyncMock)
            ),
        )


@pytest.mark.parametrize(
    "roles",
    [
        pytest.param(["ADMIN_SCR", "CREE_DESACTIVE"], id="roles_renvoyes_avec_le_role_desactive"),
        pytest.param(["ADMIN_SCR"], id="roles_renvoyes_sans_le_role_desactive"),
    ],
)
async def test_admin_modifie_son_profil_en_renvoyant_ses_roles_avec_un_role_desactive(
    client: AsyncClient, roles: list[str]
) -> None:
    with _environnement() as ecritures:
        response = await client.put(
            f"{URL}/1",
            headers=_token(_compte(["ADMIN_SCR"])),
            json={"nom": "Nouveau nom", "roles": [_attribution(nom) for nom in roles]},
        )
    assert response.status_code == 200, f"Attendu 200, obtenu {response.status_code} : {response.text}"
    ecritures.update_profile.assert_awaited_once()
    ecritures.replace_roles.assert_not_awaited()


async def test_admin_s_ajoute_un_role_meme_avec_un_role_desactive(client: AsyncClient) -> None:
    """Décision du 26/11/2026 : ajouter un autre rôle à son propre compte → 200, rôles écrits
    (le rôle désactivé qu'il détient déjà et renvoie est conservé, pas refusé en 422), audit."""
    with _environnement() as ecritures:
        response = await client.put(
            f"{URL}/1",
            headers=_token(_compte(["ADMIN_SCR"])),
            json={
                "nom": "Nouveau nom",
                "roles": [_attribution("ADMIN_SCR"), _attribution("CREE_DESACTIVE"), _attribution("CREE_SANS_DROIT")],
            },
        )
    assert response.status_code == 200, f"Attendu 200, obtenu {response.status_code} : {response.text}"
    ecritures.update_profile.assert_awaited_once()
    ecritures.replace_roles.assert_awaited_once()
    args = ecritures.replace_roles.await_args.args
    assert args[1] == 1
    assert set(args[2]) == {(CATALOGUE[nom][0], None) for nom in ("ADMIN_SCR", "CREE_DESACTIVE", "CREE_SANS_DROIT")}
    ecritures.log_audit.assert_awaited_once()
    assert ecritures.log_audit.await_args.kwargs["user_id"] == 1
