"""Droits des comptes sur une vraie base SQLite en mémoire (aiosqlite).

- `admin_utilisateur_repository.list_by_direction` : un compte relève d'une direction si tous ses
  rôles SIRV2 sont dans la direction ET chaque rôle créé relève de la direction d'après ses droits
  (propres distribution = interruptions_distribution, napt, indicateurs, assistant ; propres
  transport = interruptions_transport ; partagées = rapports, notifications, reseau ; réservées =
  admin_roles, admin_utilisateurs ; rôle créé sans droit = les deux directions).
- `utilisateur_repository.get_by_id` / `get_by_login` (compte connecté) : seuls les rôles actifs
  sont chargés.
- `admin_utilisateur_repository.get_by_id` (cible vue par l'administration) : tous les rôles,
  actifs ou non, avec leurs droits chargés (pas de chargement paresseux en async).
"""

import pytest
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.repositories import admin_utilisateur_repository as admin_repo
from app.repositories import utilisateur_repository

pytestmark = pytest.mark.asyncio

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
)

# Rôles : (id, nom, actif)
_ROLES = [
    (1, "ADMIN_SCR", 1),
    (3, "SUPERADMIN", 1),
    (10, "BCC", 1),
    (13, "DISPATCHER", 1),
    (50, "CREE_SANS_DROIT", 1),
    (53, "CREE_DISTRIB_READ", 1),
    (55, "CREE_RAPPORTS", 1),
    (57, "CREE_TRANSPORT_READ", 1),
    (58, "CREE_ADMIN_ROLES_READ", 1),
    (60, "CREE_INDIC_DESACTIVE", 0),
]
_PERMISSIONS = [
    (1, "rapports", "read"),
    (2, "interruptions_transport", "read"),
    (3, "interruptions_distribution", "read"),
    (4, "admin_roles", "read"),
    (5, "indicateurs", "read"),
]
# (role_id, permission_id)
_ROLE_PERMISSIONS = [(55, 1), (57, 2), (53, 3), (58, 4), (60, 5)]

# Comptes : login → rôles
_COMPTES: dict[str, list[str]] = {
    "bcc_seul": ["BCC"],
    "dispatcher_seul": ["DISPATCHER"],
    "dispatcher_admin_scr": ["DISPATCHER", "ADMIN_SCR"],
    "bcc_cree_rapports": ["BCC", "CREE_RAPPORTS"],
    "cree_sans_droit_seul": ["CREE_SANS_DROIT"],
    "cree_transport_seul": ["CREE_TRANSPORT_READ"],
    "bcc_cree_transport": ["BCC", "CREE_TRANSPORT_READ"],
    "aucun_role": [],
    "superadmin_cree_sans_droit": ["SUPERADMIN", "CREE_SANS_DROIT"],
    # Compléments à la spécification
    "cree_distribution_seul": ["CREE_DISTRIB_READ"],
    "cree_admin_roles_seul": ["CREE_ADMIN_ROLES_READ"],
    "bcc_cree_desactive": ["BCC", "CREE_INDIC_DESACTIVE"],
}

ATTENDU_DISTRIBUTION = {
    "bcc_seul",
    "bcc_cree_rapports",
    "cree_sans_droit_seul",
    "cree_distribution_seul",
    "bcc_cree_desactive",  # indicateurs = propre distribution
}
ATTENDU_TRANSPORT = {"dispatcher_seul", "cree_sans_droit_seul", "cree_transport_seul"}


@pytest.fixture
async def engine():
    moteur = create_async_engine("sqlite+aiosqlite://", execution_options={"schema_translate_map": {"dbo": None}})
    ids_roles = {nom: rid for rid, nom, _ in _ROLES}
    async with moteur.begin() as conn:
        for ddl in _DDL:
            await conn.exec_driver_sql(ddl)
        for rid, nom, actif in _ROLES:
            await conn.exec_driver_sql(
                "INSERT INTO roles (id, nom, description, is_active) VALUES (?, ?, ?, ?)", (rid, nom, nom, actif)
            )
        for pid, ressource, action in _PERMISSIONS:
            await conn.exec_driver_sql(
                "INSERT INTO permissions (id, ressource, action) VALUES (?, ?, ?)", (pid, ressource, action)
            )
        for i, (rid, pid) in enumerate(_ROLE_PERMISSIONS, start=1):
            await conn.exec_driver_sql(
                "INSERT INTO role_permissions (id, role_id, permission_id) VALUES (?, ?, ?)", (i, rid, pid)
            )
        ur_id = 0
        for uid, (login, roles) in enumerate(_COMPTES.items(), start=1):
            await conn.exec_driver_sql(
                "INSERT INTO utilisateurs (id, login, password_hash, nom, prenom, is_active, premiere_connexion) "
                "VALUES (?, ?, 'x', ?, 'Prenom', 1, 0)",
                (uid, login, login),
            )
            for nom in roles:
                ur_id += 1
                scope = 1 if nom == "BCC" else None
                await conn.exec_driver_sql(
                    "INSERT INTO user_roles (id, utilisateur_id, role_id, scope_service_id) VALUES (?, ?, ?, ?)",
                    (ur_id, uid, ids_roles[nom], scope),
                )
    yield moteur
    await moteur.dispose()


def _id_compte(login: str) -> int:
    return list(_COMPTES).index(login) + 1


# ---------------------------------------------------------------------------
# list_by_direction
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("direction", "attendu"),
    [
        pytest.param("distribution", ATTENDU_DISTRIBUTION, id="distribution"),
        pytest.param("transport", ATTENDU_TRANSPORT, id="transport"),
    ],
)
async def test_list_by_direction_exclut_les_roles_crees_hors_direction(engine, direction: str, attendu: set[str]) -> None:
    async with AsyncSession(engine) as db:
        comptes, total = await admin_repo.list_by_direction(db, direction, page=1, page_size=100)
        logins = {c.login for c in comptes}
    assert logins == attendu, f"En trop : {logins - attendu} ; manquants : {attendu - logins}"
    assert total == len(attendu)


async def test_list_by_direction_pagine_sur_le_meme_total(engine) -> None:
    async with AsyncSession(engine) as db:
        page1, total = await admin_repo.list_by_direction(db, "distribution", page=1, page_size=2)
    assert total == len(ATTENDU_DISTRIBUTION)
    assert len(page1) == 2


# ---------------------------------------------------------------------------
# Compte connecté : seuls les rôles actifs
# ---------------------------------------------------------------------------


async def test_utilisateur_repository_get_by_id_ne_charge_que_les_roles_actifs(engine) -> None:
    async with AsyncSession(engine) as db:
        compte = await utilisateur_repository.get_by_id(db, _id_compte("bcc_cree_desactive"))
        noms = [ur.role.nom for ur in compte.user_roles]
    assert noms == ["BCC"]


async def test_utilisateur_repository_get_by_login_ne_charge_que_les_roles_actifs(engine) -> None:
    async with AsyncSession(engine) as db:
        compte = await utilisateur_repository.get_by_login(db, "bcc_cree_desactive")
        noms = [ur.role.nom for ur in compte.user_roles]
    assert noms == ["BCC"]


async def test_utilisateur_repository_garde_les_droits_des_roles_actifs(engine) -> None:
    """Garde : les droits des rôles actifs restent chargés (rapports:read du rôle créé actif)."""
    async with AsyncSession(engine) as db:
        compte = await utilisateur_repository.get_by_id(db, _id_compte("bcc_cree_rapports"))
        droits = {
            (rp.permission.ressource, rp.permission.action)
            for ur in compte.user_roles
            for rp in ur.role.role_permissions
        }
    assert droits == {("rapports", "read")}


# ---------------------------------------------------------------------------
# Cible vue par l'administration : tous les rôles, droits chargés
# ---------------------------------------------------------------------------


async def test_admin_get_by_id_charge_tous_les_roles_meme_desactives(engine) -> None:
    async with AsyncSession(engine) as db:
        cible = await admin_repo.get_by_id(db, _id_compte("bcc_cree_desactive"))
        noms = sorted(ur.role.nom for ur in cible.user_roles)
    assert noms == ["BCC", "CREE_INDIC_DESACTIVE"]


async def test_admin_get_by_id_charge_les_droits_des_roles(engine) -> None:
    async with AsyncSession(engine) as db:
        cible = await admin_repo.get_by_id(db, _id_compte("bcc_cree_transport"))
        for ur in cible.user_roles:
            assert "role_permissions" not in inspect(ur.role).unloaded, f"Droits du rôle {ur.role.nom} non chargés"
            for rp in ur.role.role_permissions:
                assert "permission" not in inspect(rp).unloaded, (
                    f"Permission du rôle {ur.role.nom} non chargée (chargement paresseux impossible en async)"
                )
        droits = {
            (rp.permission.ressource, rp.permission.action)
            for ur in cible.user_roles
            for rp in ur.role.role_permissions
        }
    assert droits == {("interruptions_transport", "read")}


async def test_admin_get_role_by_id_charge_les_droits_du_role(engine) -> None:
    """Le contrôle d'attribution d'un rôle créé lit ses droits : ils doivent être chargés."""
    async with AsyncSession(engine) as db:
        role = await admin_repo.get_role_by_id(db, 57)
        assert "role_permissions" not in inspect(role).unloaded
        for rp in role.role_permissions:
            assert "permission" not in inspect(rp).unloaded, (
                "Permission du rôle non chargée (chargement paresseux impossible en async)"
            )
        droits = {(rp.permission.ressource, rp.permission.action) for rp in role.role_permissions}
    assert droits == {("interruptions_transport", "read")}
