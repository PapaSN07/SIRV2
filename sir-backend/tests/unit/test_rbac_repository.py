"""Tests unitaires — rbac_repository.py

Vérifie le comportement de chaque fonction du repository RBAC
en mockant la session SQLAlchemy async. Aucune connexion DB réelle.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.utilisateurs import Permission, Role, RolePermission, UserRole
from app.repositories.rbac_repository import (
    get_permission_by_key,
    get_role_by_name,
    get_user_permissions,
    get_user_roles,
    get_user_scope,
)


# ---------------------------------------------------------------------------
# Helpers de construction d'objets ORM sans session DB
# ---------------------------------------------------------------------------


def _make_permission(ressource: str, action: str, perm_id: int = 1) -> Permission:
    perm = Permission()
    perm.id = perm_id
    perm.ressource = ressource
    perm.action = action
    perm.description = f"{ressource}:{action}"
    perm.role_permissions = []
    return perm


def _make_role_with_permissions(
    nom: str,
    role_id: int,
    raw_permissions: list[tuple[str, str]],
) -> Role:
    """Construit un Role avec ses RolePermission et Permission liés."""
    role = Role()
    role.id = role_id
    role.nom = nom
    role.description = f"Rôle {nom}"
    role.is_active = True

    rp_list: list[RolePermission] = []
    for i, (ressource, action) in enumerate(raw_permissions, start=1):
        perm = _make_permission(ressource, action, perm_id=i)
        rp = RolePermission()
        rp.id = i
        rp.role_id = role_id
        rp.permission_id = perm.id
        rp.role = role
        rp.permission = perm
        perm.role_permissions = [rp]
        rp_list.append(rp)

    role.role_permissions = rp_list
    return role


def _make_user_role(
    role: Role,
    utilisateur_id: int = 1,
    scope_service_id: int | None = 1,
) -> UserRole:
    ur = UserRole()
    ur.id = 1
    ur.utilisateur_id = utilisateur_id
    ur.role_id = role.id
    ur.scope_service_id = scope_service_id
    ur.role = role
    return ur


def _make_mock_db_with_scalars(scalars_result: list) -> AsyncMock:
    """Crée une AsyncMock de session dont execute() retourne scalars().all() = scalars_result."""
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = scalars_result

    db = AsyncMock()
    db.execute = AsyncMock(return_value=mock_result)
    return db


def _make_mock_db_with_scalar_one_or_none(value) -> AsyncMock:
    """Crée une AsyncMock de session dont execute() retourne scalar_one_or_none() = value."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = value

    db = AsyncMock()
    db.execute = AsyncMock(return_value=mock_result)
    return db


def _make_mock_db_with_scalar(value) -> AsyncMock:
    """Crée une AsyncMock dont execute() retourne scalar() = value (pour get_user_scope)."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = value

    db = AsyncMock()
    db.execute = AsyncMock(return_value=mock_result)
    return db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def role_bcc() -> Role:
    return _make_role_with_permissions(
        nom="BCC",
        role_id=1,
        raw_permissions=[
            ("interruptions_distribution", "create"),
            ("interruptions_distribution", "read"),
            ("interruptions_distribution", "update"),
        ],
    )


@pytest.fixture
def role_admin_scr() -> Role:
    return _make_role_with_permissions(
        nom="ADMIN_SCR",
        role_id=3,
        raw_permissions=[
            ("interruptions_distribution", "create"),
            ("interruptions_distribution", "read"),
            ("interruptions_distribution", "update"),
            ("interruptions_distribution", "validate"),
        ],
    )


@pytest.fixture
def role_inexistant() -> None:
    return None


# ---------------------------------------------------------------------------
# Tests : get_user_permissions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_user_permissions_retourne_liste_correcte_pour_bcc(
    role_bcc: Role,
) -> None:
    """get_user_permissions pour un BCC retourne les 3 permissions attendues triées."""
    ur = _make_user_role(role_bcc, utilisateur_id=1, scope_service_id=1)
    db = _make_mock_db_with_scalars([ur])

    permissions = await get_user_permissions(db, user_id=1)

    assert permissions == [
        "interruptions_distribution:create",
        "interruptions_distribution:read",
        "interruptions_distribution:update",
    ]


@pytest.mark.asyncio
async def test_get_user_permissions_retourne_liste_vide_si_aucun_role() -> None:
    """get_user_permissions sans user_roles retourne une liste vide."""
    db = _make_mock_db_with_scalars([])

    permissions = await get_user_permissions(db, user_id=99)

    assert permissions == []


@pytest.mark.asyncio
async def test_get_user_permissions_deduplique_permissions_multi_roles(
    role_bcc: Role,
) -> None:
    """Un utilisateur multi-rôles avec permissions communes ne reçoit pas de doublons."""
    # Deuxième rôle avec une permission qui recouvre celle de BCC
    role_brc = _make_role_with_permissions(
        nom="BRC",
        role_id=2,
        raw_permissions=[
            ("interruptions_distribution", "read"),  # existe déjà dans BCC
        ],
    )
    ur_bcc = _make_user_role(role_bcc, utilisateur_id=10, scope_service_id=1)
    ur_bcc.id = 1
    ur_brc = _make_user_role(role_brc, utilisateur_id=10, scope_service_id=3)
    ur_brc.id = 2

    db = _make_mock_db_with_scalars([ur_bcc, ur_brc])

    permissions = await get_user_permissions(db, user_id=10)

    # Pas de doublon sur interruptions_distribution:read
    assert permissions.count("interruptions_distribution:read") == 1


@pytest.mark.asyncio
async def test_get_user_permissions_retourne_union_multi_roles(
    role_bcc: Role,
    role_admin_scr: Role,
) -> None:
    """Un utilisateur multi-rôles reçoit l'union des permissions de tous ses rôles."""
    ur_bcc = _make_user_role(role_bcc, utilisateur_id=10, scope_service_id=1)
    ur_bcc.id = 1
    ur_admin = _make_user_role(role_admin_scr, utilisateur_id=10, scope_service_id=None)
    ur_admin.id = 2

    db = _make_mock_db_with_scalars([ur_bcc, ur_admin])

    permissions = await get_user_permissions(db, user_id=10)

    # validate vient uniquement d'ADMIN_SCR
    assert "interruptions_distribution:validate" in permissions
    # create, read, update sont dans les deux rôles — toujours présents une fois
    assert permissions.count("interruptions_distribution:create") == 1


# ---------------------------------------------------------------------------
# Tests : get_user_roles
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_user_roles_retourne_bcc_pour_utilisateur_bcc(
    role_bcc: Role,
) -> None:
    """get_user_roles retourne ["BCC"] pour un utilisateur avec le rôle BCC."""
    ur = _make_user_role(role_bcc, utilisateur_id=1, scope_service_id=1)
    db = _make_mock_db_with_scalars([ur])

    roles = await get_user_roles(db, user_id=1)

    assert roles == ["BCC"]


@pytest.mark.asyncio
async def test_get_user_roles_retourne_liste_vide_si_aucun_role() -> None:
    """get_user_roles retourne [] pour un utilisateur sans rôle."""
    db = _make_mock_db_with_scalars([])

    roles = await get_user_roles(db, user_id=99)

    assert roles == []


@pytest.mark.asyncio
async def test_get_user_roles_retourne_plusieurs_roles_si_multi_roles(
    role_bcc: Role,
    role_admin_scr: Role,
) -> None:
    """get_user_roles retourne tous les rôles pour un utilisateur multi-rôles."""
    ur_bcc = _make_user_role(role_bcc, utilisateur_id=10, scope_service_id=1)
    ur_bcc.id = 1
    ur_admin = _make_user_role(role_admin_scr, utilisateur_id=10, scope_service_id=None)
    ur_admin.id = 2

    db = _make_mock_db_with_scalars([ur_bcc, ur_admin])

    roles = await get_user_roles(db, user_id=10)

    assert set(roles) == {"BCC", "ADMIN_SCR"}


# ---------------------------------------------------------------------------
# Tests : get_user_scope
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_user_scope_retourne_scope_service_id_pour_bcc() -> None:
    """get_user_scope retourne 1 pour un BCC avec scope_service_id=1."""
    db = _make_mock_db_with_scalar(1)

    scope = await get_user_scope(db, user_id=1)

    assert scope == 1


@pytest.mark.asyncio
async def test_get_user_scope_retourne_none_pour_role_national() -> None:
    """get_user_scope retourne None pour ADMIN_SCR (scope_service_id=NULL en DB)."""
    db = _make_mock_db_with_scalar(None)

    scope = await get_user_scope(db, user_id=4)

    assert scope is None


@pytest.mark.asyncio
async def test_get_user_scope_retourne_none_si_aucun_user_role() -> None:
    """get_user_scope retourne None quand l'utilisateur n'a aucun user_role."""
    db = _make_mock_db_with_scalar(None)

    scope = await get_user_scope(db, user_id=99)

    assert scope is None


# ---------------------------------------------------------------------------
# Tests : get_role_by_name
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_role_by_name_retourne_role_bcc(role_bcc: Role) -> None:
    """get_role_by_name("BCC") retourne le rôle avec ses permissions."""
    db = _make_mock_db_with_scalar_one_or_none(role_bcc)

    role = await get_role_by_name(db, "BCC")

    assert role is not None
    assert role.nom == "BCC"
    # Le rôle doit porter ses role_permissions
    assert len(role.role_permissions) == 3
    perm_keys = {
        f"{rp.permission.ressource}:{rp.permission.action}"
        for rp in role.role_permissions
    }
    assert perm_keys == {
        "interruptions_distribution:create",
        "interruptions_distribution:read",
        "interruptions_distribution:update",
    }


@pytest.mark.asyncio
async def test_get_role_by_name_retourne_none_si_role_inexistant() -> None:
    """get_role_by_name("INEXISTANT") retourne None."""
    db = _make_mock_db_with_scalar_one_or_none(None)

    role = await get_role_by_name(db, "INEXISTANT")

    assert role is None


@pytest.mark.asyncio
async def test_get_role_by_name_admin_scr_a_permission_validate(
    role_admin_scr: Role,
) -> None:
    """get_role_by_name("ADMIN_SCR") retourne un rôle avec interruptions_distribution:validate."""
    db = _make_mock_db_with_scalar_one_or_none(role_admin_scr)

    role = await get_role_by_name(db, "ADMIN_SCR")

    assert role is not None
    perm_keys = {
        f"{rp.permission.ressource}:{rp.permission.action}"
        for rp in role.role_permissions
    }
    assert "interruptions_distribution:validate" in perm_keys


# ---------------------------------------------------------------------------
# Tests : get_permission_by_key
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_permission_by_key_retourne_permission_existante() -> None:
    """get_permission_by_key("interruptions_distribution", "read") retourne la permission."""
    perm = _make_permission("interruptions_distribution", "read", perm_id=2)
    db = _make_mock_db_with_scalar_one_or_none(perm)

    result = await get_permission_by_key(db, "interruptions_distribution", "read")

    assert result is not None
    assert result.ressource == "interruptions_distribution"
    assert result.action == "read"


@pytest.mark.asyncio
async def test_get_permission_by_key_retourne_none_si_inexistante() -> None:
    """get_permission_by_key sur une paire inexistante retourne None."""
    db = _make_mock_db_with_scalar_one_or_none(None)

    result = await get_permission_by_key(db, "module_inexistant", "delete")

    assert result is None


# ---------------------------------------------------------------------------
# Test idempotence : seed_rbac exécuté deux fois ne crée pas de doublons
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_seed_rbac_idempotent_ne_cree_pas_de_doublons() -> None:
    """seed_rbac() exécuté deux fois ne crée aucun doublon (7 rôles, 17 permissions).

    On vérifie que les appels upsert ne font pas de db.add() supplémentaire
    si les objets existent déjà en base.
    """
    from app.models.seed.seed_rbac import _PERMISSIONS, _ROLES, seed_rbac

    db = AsyncMock()
    db.flush = AsyncMock()
    next_id = iter(range(1, 10_000))

    def _add(obj) -> None:
        # Simule l'id attribué par la base au flush (sinon toutes les
        # associations rôle↔permission ont la clé (None, None) et sont dédupliquées)
        if getattr(obj, "id", None) is None:
            obj.id = next(next_id)

    db.add = MagicMock(side_effect=_add)  # Suivre les appels

    call_count: int = 0

    async def _fake_execute(stmt):
        nonlocal call_count
        call_count += 1
        mock_result = MagicMock()

        # Extraire ce qu'on cherche à partir du type de la stmt via whereclause
        # Approche simplifiée : on imite le comportement upsert en retournant
        # None la première fois (création) et l'objet existant la deuxième fois.
        # Le test principal est que db.add() est appelé une seule fois par objet.
        mock_result.scalar_one_or_none.return_value = None
        return mock_result

    db.execute = _fake_execute

    # Premier appel — doit créer tous les objets
    await seed_rbac(db)
    first_run_add_count = db.add.call_count

    # Vérifier que tous les objets attendus ont été créés
    expected_permissions = len(_PERMISSIONS)
    expected_roles = len(_ROLES)
    # Chaque permission créée + chaque rôle créé + chaque association
    total_expected_additions = (
        expected_permissions
        + expected_roles
        + sum(len(perms) for _, _, perms in _ROLES)
    )
    assert first_run_add_count == total_expected_additions, (
        f"Premier run : {first_run_add_count} ajouts, attendu {total_expected_additions}"
    )

    # Simuler le deuxième appel avec une DB déjà peuplée
    db2 = AsyncMock()
    db2.flush = AsyncMock()
    db2.add = MagicMock()

    # Construire les objets "existants" pour le deuxième run
    perm_objects: dict[tuple[str, str], Permission] = {}
    role_objects: dict[str, Role] = {}
    rp_objects: set[tuple[int, int]] = set()

    for i, (ressource, action, description) in enumerate(_PERMISSIONS, start=1):
        perm = Permission()
        perm.id = i
        perm.ressource = ressource
        perm.action = action
        perm.description = description
        perm_objects[(ressource, action)] = perm

    for j, (nom_role, description_role, role_perms) in enumerate(_ROLES, start=1):
        role = Role()
        role.id = j
        role.nom = nom_role
        role.description = description_role
        role.is_active = True
        role_objects[nom_role] = role
        for ressource, action in role_perms:
            rp_objects.add((j, perm_objects[(ressource, action)].id))

    execute_call_index: list[int] = [0]

    # Ordre des requêtes dans seed_rbac :
    # 1) une requête par permission (upsert)
    # 2) une seule requête qui charge toutes les associations rôle↔permission
    # 3) une requête par rôle (upsert) ; les associations sont vérifiées en mémoire
    call_sequence: list = [("permission", perm) for perm in perm_objects.values()]
    call_sequence.append(("links", sorted(rp_objects)))
    call_sequence.extend(("role", role_objects[nom_role]) for nom_role, _, _ in _ROLES)

    async def _fake_execute_second_run(stmt):
        idx = execute_call_index[0]
        execute_call_index[0] += 1
        mock_result = MagicMock()
        kind, obj = call_sequence[idx] if idx < len(call_sequence) else (None, None)
        if kind == "links":
            mock_result.all.return_value = obj
        else:
            mock_result.scalar_one_or_none.return_value = obj
        return mock_result

    db2.execute = _fake_execute_second_run

    # Deuxième appel — aucun db2.add() ne doit être appelé
    await seed_rbac(db2)
    assert db2.add.call_count == 0, (
        f"Deuxième run idempotent : {db2.add.call_count} ajouts inattendus"
    )
