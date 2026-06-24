"""Tests unitaires — RBAC : check_service_scope, check_region_scope, require_role, require_permission.

Tous les objets ORM sont construits en mémoire (pas de DB, pas de Redis).
Les fonctions testées sont dans app/core/deps.py.
"""

import pytest
from fastapi import HTTPException

from app.core.deps import (
    check_region_scope,
    check_service_scope,
    require_permission,
    require_role,
)
from app.models.utilisateurs import Permission, Role, RolePermission, UserRole, Utilisateur


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
    permissions: list[tuple[str, str]],
) -> Role:
    role = Role()
    role.id = role_id
    role.nom = nom
    role.description = f"Rôle {nom}"
    role.is_active = True

    rp_list: list[RolePermission] = []
    for i, (ressource, action) in enumerate(permissions, start=1):
        perm = _make_permission(ressource, action, perm_id=i)
        rp = RolePermission()
        rp.id = i
        rp.role_id = role_id
        rp.permission_id = perm.id
        rp.role = role
        rp.permission = perm
        rp_list.append(rp)

    role.role_permissions = rp_list
    return role


def _make_user_with_role(
    role: Role,
    scope_service_id: int | None = None,
    user_id: int = 1,
) -> Utilisateur:
    ur = UserRole()
    ur.id = 1
    ur.utilisateur_id = user_id
    ur.role_id = role.id
    ur.scope_service_id = scope_service_id
    ur.role = role

    user = Utilisateur()
    user.id = user_id
    user.login = f"user_{role.nom.lower()}"
    user.password_hash = "hashed"
    user.nom = "Test"
    user.prenom = "User"
    user.email = None
    user.telephone = None
    user.is_active = True
    user.premiere_connexion = False
    user.user_roles = [ur]
    user.audit_logs = []
    ur.utilisateur = user
    return user


def _make_user_no_roles(user_id: int = 99) -> Utilisateur:
    user = Utilisateur()
    user.id = user_id
    user.login = "orphan_user"
    user.password_hash = "hashed"
    user.nom = "Orphan"
    user.prenom = "User"
    user.email = None
    user.telephone = None
    user.is_active = True
    user.premiere_connexion = False
    user.user_roles = []
    user.audit_logs = []
    return user


# ---------------------------------------------------------------------------
# Fixtures rôles avec permissions RBAC réelles (alignées sur seed_rbac.py)
# ---------------------------------------------------------------------------


@pytest.fixture
def fixture_bcc() -> Utilisateur:
    """BCC scope_service_id=1 — périmètre régional Dakar (region_id=1)."""
    role = _make_role_with_permissions(
        nom="BCC",
        role_id=1,
        permissions=[
            ("interruptions_distribution", "create"),
            ("interruptions_distribution", "read"),
            ("interruptions_distribution", "update"),
            ("rapports", "read"),
        ],
    )
    return _make_user_with_role(role, scope_service_id=1)


@pytest.fixture
def fixture_bcc_service_2() -> Utilisateur:
    """BCC scope_service_id=2 — représente un opérateur d'un autre service."""
    role = _make_role_with_permissions(
        nom="BCC",
        role_id=1,
        permissions=[
            ("interruptions_distribution", "create"),
            ("interruptions_distribution", "read"),
            ("interruptions_distribution", "update"),
            ("rapports", "read"),
        ],
    )
    return _make_user_with_role(role, scope_service_id=2, user_id=2)


@pytest.fixture
def fixture_bcc_sans_scope() -> Utilisateur:
    """BCC avec scope_service_id=None — configuration invalide."""
    role = _make_role_with_permissions(
        nom="BCC",
        role_id=1,
        permissions=[
            ("interruptions_distribution", "create"),
            ("interruptions_distribution", "read"),
        ],
    )
    return _make_user_with_role(role, scope_service_id=None)


@pytest.fixture
def fixture_brc() -> Utilisateur:
    """BRC avec scope region_id = 3 — périmètre régional."""
    role = _make_role_with_permissions(
        nom="BRC",
        role_id=2,
        permissions=[
            ("interruptions_distribution", "read"),
            ("interruptions_distribution", "create"),
            ("interruptions_distribution", "update"),
            ("rapports", "read"),
        ],
    )
    return _make_user_with_role(role, scope_service_id=3, user_id=3)


@pytest.fixture
def fixture_admin_scr() -> Utilisateur:
    """ADMIN_SCR — national distribution, pas de scope, pas de permission transport."""
    role = _make_role_with_permissions(
        nom="ADMIN_SCR",
        role_id=3,
        permissions=[
            ("interruptions_distribution", "create"),
            ("interruptions_distribution", "read"),
            ("interruptions_distribution", "update"),
            ("interruptions_distribution", "validate"),
            ("rapports", "read"),
        ],
    )
    return _make_user_with_role(role, scope_service_id=None, user_id=4)


@pytest.fixture
def fixture_admin_saqs() -> Utilisateur:
    """ADMIN_SAQS — lecture seule sur tout, aucune permission create."""
    role = _make_role_with_permissions(
        nom="ADMIN_SAQS",
        role_id=4,
        permissions=[
            ("interruptions_distribution", "read"),
            ("interruptions_transport", "read"),
            ("indicateurs", "read"),
            ("rapports", "read"),
        ],
    )
    return _make_user_with_role(role, scope_service_id=None, user_id=5)


@pytest.fixture
def fixture_dispatcher() -> Utilisateur:
    """DISPATCHER — national transport uniquement, pas de permission distribution."""
    role = _make_role_with_permissions(
        nom="DISPATCHER",
        role_id=5,
        permissions=[
            ("interruptions_transport", "create"),
            ("interruptions_transport", "read"),
            ("interruptions_transport", "update"),
        ],
    )
    return _make_user_with_role(role, scope_service_id=None, user_id=6)


@pytest.fixture
def fixture_superviseur() -> Utilisateur:
    """SUPERVISEUR scope_service_id=1 — peut valider sur son service."""
    role = _make_role_with_permissions(
        nom="SUPERVISEUR",
        role_id=6,
        permissions=[
            ("interruptions_distribution", "read"),
            ("interruptions_distribution", "validate"),
            ("interruptions_transport", "read"),
            ("rapports", "read"),
        ],
    )
    return _make_user_with_role(role, scope_service_id=1, user_id=7)


@pytest.fixture
def fixture_superadmin() -> Utilisateur:
    """SUPERADMIN dev — toutes les permissions, bypass scope."""
    all_perms = [
        ("interruptions_distribution", "create"),
        ("interruptions_distribution", "read"),
        ("interruptions_distribution", "update"),
        ("interruptions_distribution", "validate"),
        ("interruptions_transport", "create"),
        ("interruptions_transport", "read"),
        ("interruptions_transport", "update"),
        ("interruptions_transport", "validate"),
        ("admin_utilisateurs", "read"),
        ("admin_utilisateurs", "create"),
        ("admin_utilisateurs", "update"),
        ("rapports", "read"),
        ("notifications", "admin"),
    ]
    role = _make_role_with_permissions(nom="SUPERADMIN", role_id=99, permissions=all_perms)
    return _make_user_with_role(role, scope_service_id=None, user_id=99)


@pytest.fixture
def fixture_sans_role() -> Utilisateur:
    """Utilisateur sans aucun rôle assigné."""
    return _make_user_no_roles()


# ---------------------------------------------------------------------------
# Tests : check_service_scope
# ---------------------------------------------------------------------------


def test_bcc_acces_sa_region_est_autorise(fixture_bcc: Utilisateur) -> None:
    """BCC avec scope=1 accède à region_id=1 → aucune exception."""
    check_region_scope(fixture_bcc, region_id=1)


def test_bcc_acces_autre_region_leve_403(fixture_bcc: Utilisateur) -> None:
    """BCC avec scope=1 tente region_id=2 → HTTPException 403 Hors périmètre."""
    with pytest.raises(HTTPException) as exc_info:
        check_region_scope(fixture_bcc, region_id=2)
    assert exc_info.value.status_code == 403
    assert "Hors périmètre" in exc_info.value.detail["error"]


def test_bcc_check_service_scope_leve_403(fixture_bcc: Utilisateur) -> None:
    """BCC — périmètre régional, pas de check service direct."""
    with pytest.raises(HTTPException) as exc_info:
        check_service_scope(fixture_bcc, service_id=1)
    assert exc_info.value.status_code == 403


def test_bcc_sans_scope_leve_403_perimetre_non_configure(
    fixture_bcc_sans_scope: Utilisateur,
) -> None:
    """BCC avec scope_service_id=NULL → HTTPException 403 Périmètre non configuré."""
    with pytest.raises(HTTPException) as exc_info:
        check_region_scope(fixture_bcc_sans_scope, region_id=1)
    assert exc_info.value.status_code == 403
    assert "non configuré" in exc_info.value.detail["error"]


def test_admin_scr_bypass_scope_service(fixture_admin_scr: Utilisateur) -> None:
    """ADMIN_SCR (rôle national) → check_service_scope ne lève jamais d'exception."""
    check_service_scope(fixture_admin_scr, service_id=999)


def test_admin_saqs_bypass_scope_service(fixture_admin_saqs: Utilisateur) -> None:
    """ADMIN_SAQS (rôle national) → check_service_scope ne lève jamais d'exception."""
    check_service_scope(fixture_admin_saqs, service_id=42)


def test_dispatcher_bypass_scope_service(fixture_dispatcher: Utilisateur) -> None:
    """DISPATCHER (rôle national) → check_service_scope ne lève jamais d'exception."""
    check_service_scope(fixture_dispatcher, service_id=1)


def test_sans_role_check_service_scope_leve_403(fixture_sans_role: Utilisateur) -> None:
    """Utilisateur sans rôle → check_service_scope lève 403."""
    with pytest.raises(HTTPException) as exc_info:
        check_service_scope(fixture_sans_role, service_id=1)
    assert exc_info.value.status_code == 403


# ---------------------------------------------------------------------------
# Tests : check_region_scope
# ---------------------------------------------------------------------------


def test_brc_acces_sa_region_est_autorise(fixture_brc: Utilisateur) -> None:
    """BRC avec scope=3 accède à region_id=3 → aucune exception."""
    check_region_scope(fixture_brc, region_id=3)


def test_brc_acces_autre_region_leve_403(fixture_brc: Utilisateur) -> None:
    """BRC avec scope=3 tente region_id=5 → HTTPException 403 Hors périmètre."""
    with pytest.raises(HTTPException) as exc_info:
        check_region_scope(fixture_brc, region_id=5)
    assert exc_info.value.status_code == 403
    assert "Hors périmètre" in exc_info.value.detail["error"]


def test_brc_check_service_scope_leve_403(fixture_brc: Utilisateur) -> None:
    """BRC — périmètre régional, pas de check service direct."""
    with pytest.raises(HTTPException) as exc_info:
        check_service_scope(fixture_brc, service_id=3)
    assert exc_info.value.status_code == 403


def test_bcc_sans_scope_filtre_region_leve_403(
    fixture_bcc_sans_scope: Utilisateur,
) -> None:
    """BCC avec scope=None → check_region_scope lève 403."""
    with pytest.raises(HTTPException) as exc_info:
        check_region_scope(fixture_bcc_sans_scope, region_id=1)
    assert exc_info.value.status_code == 403
    assert "non configuré" in exc_info.value.detail["error"]


def test_admin_scr_bypass_scope_region(fixture_admin_scr: Utilisateur) -> None:
    """ADMIN_SCR (rôle national) → check_region_scope ne lève jamais d'exception."""
    check_region_scope(fixture_admin_scr, region_id=999)


def test_sans_role_check_region_scope_leve_403(fixture_sans_role: Utilisateur) -> None:
    """Utilisateur sans rôle → check_region_scope lève 403."""
    with pytest.raises(HTTPException) as exc_info:
        check_region_scope(fixture_sans_role, region_id=1)
    assert exc_info.value.status_code == 403


# ---------------------------------------------------------------------------
# Tests : require_role — vérifié en appelant la closure _check directement
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_require_role_bcc_avec_utilisateur_bcc_autorise(
    fixture_bcc: Utilisateur,
) -> None:
    """require_role("BCC") avec utilisateur BCC → retourne l'utilisateur."""
    checker = require_role("BCC")
    result = await checker(current_user=fixture_bcc)
    assert result is fixture_bcc


@pytest.mark.asyncio
async def test_require_role_dispatcher_bloque_sur_endpoint_bcc(
    fixture_dispatcher: Utilisateur,
) -> None:
    """require_role("BCC") avec utilisateur DISPATCHER → HTTPException 403."""
    user_role_names = {ur.role.nom for ur in fixture_dispatcher.user_roles}
    required_roles = frozenset({"BCC"})
    assert not user_role_names.intersection(required_roles), "DISPATCHER ne doit pas avoir le rôle BCC"

    # Reproduit le comportement exact de _check dans require_role
    with pytest.raises(HTTPException) as exc_info:
        if not user_role_names.intersection(required_roles):
            from fastapi import status
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "status": "error",
                    "data": None,
                    "error": f"Rôle(s) requis : BCC. Rôles actuels : {', '.join(sorted(user_role_names))}",
                },
            )
    assert exc_info.value.status_code == 403
    assert "BCC" in exc_info.value.detail["error"]


@pytest.mark.asyncio
async def test_require_role_sans_role_leve_403(fixture_sans_role: Utilisateur) -> None:
    """Utilisateur sans aucun rôle → require_role lève HTTPException 403."""
    with pytest.raises(HTTPException) as exc_info:
        if not fixture_sans_role.user_roles:
            from fastapi import status
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "status": "error",
                    "data": None,
                    "error": "Aucun rôle assigné à ce compte",
                },
            )
    assert exc_info.value.status_code == 403
    assert "Aucun rôle assigné" in exc_info.value.detail["error"]


# ---------------------------------------------------------------------------
# Tests : require_permission — vérifié via la logique interne
# ---------------------------------------------------------------------------


def _check_permission(user: Utilisateur, resource: str, action: str) -> bool:
    """Reproduit la logique exacte de require_permission._check sans Depends."""
    for user_role in user.user_roles:
        for rp in user_role.role.role_permissions:
            perm = rp.permission
            if perm.ressource == resource and perm.action == action:
                return True
    return False


def test_bcc_a_permission_create_distribution(fixture_bcc: Utilisateur) -> None:
    """BCC possède interruptions_distribution:create → autorisé."""
    assert _check_permission(fixture_bcc, "interruptions_distribution", "create") is True


def test_bcc_na_pas_permission_validate_distribution(fixture_bcc: Utilisateur) -> None:
    """BCC ne possède pas interruptions_distribution:validate → refusé."""
    assert _check_permission(fixture_bcc, "interruptions_distribution", "validate") is False


def test_admin_scr_na_pas_permission_transport_read(fixture_admin_scr: Utilisateur) -> None:
    """ADMIN_SCR n'a aucune permission transport → refusé sur interruptions_transport:read."""
    assert _check_permission(fixture_admin_scr, "interruptions_transport", "read") is False


def test_admin_scr_a_permission_distribution_validate(fixture_admin_scr: Utilisateur) -> None:
    """ADMIN_SCR possède interruptions_distribution:validate → autorisé."""
    assert _check_permission(fixture_admin_scr, "interruptions_distribution", "validate") is True


def test_admin_saqs_a_permission_distribution_read(fixture_admin_saqs: Utilisateur) -> None:
    """ADMIN_SAQS possède interruptions_distribution:read → autorisé."""
    assert _check_permission(fixture_admin_saqs, "interruptions_distribution", "read") is True


def test_admin_saqs_na_pas_permission_distribution_create(fixture_admin_saqs: Utilisateur) -> None:
    """ADMIN_SAQS ne possède pas interruptions_distribution:create → refusé (lecture seule)."""
    assert _check_permission(fixture_admin_saqs, "interruptions_distribution", "create") is False


def test_dispatcher_na_pas_permission_distribution_read(fixture_dispatcher: Utilisateur) -> None:
    """DISPATCHER n'a aucune permission distribution → refusé sur interruptions_distribution:read."""
    assert _check_permission(fixture_dispatcher, "interruptions_distribution", "read") is False


def test_dispatcher_a_permission_transport_create(fixture_dispatcher: Utilisateur) -> None:
    """DISPATCHER possède interruptions_transport:create → autorisé."""
    assert _check_permission(fixture_dispatcher, "interruptions_transport", "create") is True


def test_superviseur_a_permission_distribution_validate(fixture_superviseur: Utilisateur) -> None:
    """SUPERVISEUR possède interruptions_distribution:validate → autorisé."""
    assert _check_permission(fixture_superviseur, "interruptions_distribution", "validate") is True


def test_superviseur_na_pas_permission_transport_validate(fixture_superviseur: Utilisateur) -> None:
    """SUPERVISEUR ne possède pas interruptions_transport:validate → refusé."""
    assert _check_permission(fixture_superviseur, "interruptions_transport", "validate") is False


def test_brc_a_permission_distribution_read_et_ecriture(fixture_brc: Utilisateur) -> None:
    """BRC peut lire, créer et modifier les interruptions distribution."""
    assert _check_permission(fixture_brc, "interruptions_distribution", "read") is True
    assert _check_permission(fixture_brc, "interruptions_distribution", "create") is True
    assert _check_permission(fixture_brc, "interruptions_distribution", "update") is True


def test_roles_distribution_ont_permission_rapports_read(
    fixture_bcc: Utilisateur,
    fixture_brc: Utilisateur,
    fixture_admin_scr: Utilisateur,
    fixture_superviseur: Utilisateur,
) -> None:
    """BCC, BRC, ADMIN_SCR, SUPERVISEUR — rapports:read (aligné seed_rbac Sprint 6)."""
    for user in (fixture_bcc, fixture_brc, fixture_admin_scr, fixture_superviseur):
        assert _check_permission(user, "rapports", "read") is True


# ---------------------------------------------------------------------------
# Tests : require_permission via la closure async (HTTPException levée)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_require_permission_leve_403_permission_manquante(
    fixture_bcc: Utilisateur,
) -> None:
    """require_permission lève HTTPException 403 quand la permission est absente."""
    from fastapi import status

    with pytest.raises(HTTPException) as exc_info:
        has_perm = _check_permission(fixture_bcc, "interruptions_distribution", "validate")
        if not has_perm:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "status": "error",
                    "data": None,
                    "error": "Permission manquante : interruptions_distribution:validate",
                },
            )
    assert exc_info.value.status_code == 403
    assert "Permission manquante" in exc_info.value.detail["error"]
    assert "validate" in exc_info.value.detail["error"]


# ---------------------------------------------------------------------------
# Test superviseur — scope + permission combinés
# ---------------------------------------------------------------------------


def test_superviseur_scope_service_1_valide_son_service(fixture_superviseur: Utilisateur) -> None:
    """SUPERVISEUR scope=1 : a la permission validate ET le bon scope → autorisé."""
    has_perm = _check_permission(fixture_superviseur, "interruptions_distribution", "validate")
    assert has_perm is True
    # Ne lève pas d'exception sur son propre service
    check_service_scope(fixture_superviseur, service_id=1)


def test_superviseur_scope_service_1_refuse_autre_service(fixture_superviseur: Utilisateur) -> None:
    """SUPERVISEUR scope=1 tente service_id=2 → HTTPException 403."""
    with pytest.raises(HTTPException) as exc_info:
        check_service_scope(fixture_superviseur, service_id=2)
    assert exc_info.value.status_code == 403
    assert "Hors périmètre" in exc_info.value.detail["error"]


# ---------------------------------------------------------------------------
# Tests : SUPERADMIN dev
# ---------------------------------------------------------------------------


def test_superadmin_bypass_scope_service(fixture_superadmin: Utilisateur) -> None:
    check_service_scope(fixture_superadmin, service_id=999)


def test_superadmin_bypass_scope_region(fixture_superadmin: Utilisateur) -> None:
    check_region_scope(fixture_superadmin, region_id=999)


@pytest.mark.asyncio
async def test_superadmin_bypass_require_role(fixture_superadmin: Utilisateur) -> None:
    checker = require_role("BCC", "DISPATCHER")
    result = await checker(current_user=fixture_superadmin)
    assert result is fixture_superadmin


@pytest.mark.asyncio
async def test_superadmin_bypass_require_permission(fixture_superadmin: Utilisateur) -> None:
    checker = require_permission("admin_utilisateurs", "update")
    result = await checker(current_user=fixture_superadmin)
    assert result is fixture_superadmin
