"""Tests unitaires — configuration LDAP (sans connexion AD réelle)."""

from unittest.mock import MagicMock, patch

from app.core.config import settings
from app.services import ldap_service


def test_ldap_disabled_by_default_in_tests() -> None:
    assert settings.ldap_enabled is False
    assert settings.ldap_is_configured is False


def test_ldap_hosts_list_splits_and_strips() -> None:
    with patch.object(
        settings,
        "ldap_hosts",
        " srv-siegedc0.electricite.sn , srv-datacentdc1.electricite.sn ",
    ):
        assert settings.ldap_hosts_list == [
            "srv-siegedc0.electricite.sn",
            "srv-datacentdc1.electricite.sn",
        ]


def test_verify_user_password_disabled_returns_none() -> None:
    assert ldap_service.verify_user_password("mamadou.sene2", "secret") is None


def test_verify_user_password_binds_with_user_dn() -> None:
    found = ldap_service.LdapUser(
        dn="CN=Mamadou SENE,CN=Users,DC=electricite,DC=sn",
        sam_account_name="mamadou.sene2",
        user_principal_name="mamadou.sene2@senelec.sn",
        display_name="Mamadou SENE",
        mail="mamadou.sene2@senelec.sn",
    )
    conn = MagicMock()
    conn.bind.return_value = True
    with (
        patch.object(settings, "ldap_enabled", True),
        patch.object(settings, "ldap_bind_dn", "CN=service SIP,CN=Users,DC=electricite,DC=sn"),
        patch.object(settings, "ldap_bind_password", "secret"),
        patch.object(settings, "ldap_hosts", "srv-siegedc0.electricite.sn"),
        patch("app.services.ldap_service.search_user_by_login", return_value=found),
        patch("app.services.ldap_service.Connection", return_value=conn) as connection,
    ):
        assert ldap_service.verify_user_password("mamadou.sene2", "MotDePasseAD") is True
    assert connection.call_args.kwargs["user"] == found.dn
    assert connection.call_args.kwargs["password"] == "MotDePasseAD"
    conn.unbind.assert_called_once()


def test_verify_user_password_unknown_account_returns_none() -> None:
    with (
        patch.object(settings, "ldap_enabled", True),
        patch.object(settings, "ldap_bind_dn", "CN=service SIP,CN=Users,DC=electricite,DC=sn"),
        patch.object(settings, "ldap_bind_password", "secret"),
        patch.object(settings, "ldap_hosts", "srv-siegedc0.electricite.sn"),
        patch("app.services.ldap_service.search_user_by_login", return_value=None),
    ):
        assert ldap_service.verify_user_password("inconnu", "secret") is None


def test_bind_service_account_unbinds_after_success() -> None:
    conn = MagicMock()
    conn.bind.return_value = True
    conn.server.host = "srv-siegedc0.electricite.sn"
    with (
        patch.object(settings, "ldap_enabled", True),
        patch.object(settings, "ldap_bind_dn", "CN=service SIP,CN=Users,DC=electricite,DC=sn"),
        patch.object(settings, "ldap_bind_password", "secret"),
        patch.object(settings, "ldap_hosts", "srv-siegedc0.electricite.sn"),
        patch("app.services.ldap_service.Connection", return_value=conn),
    ):
        host = ldap_service.bind_service_account()
    assert host == "srv-siegedc0.electricite.sn"
    conn.bind.assert_called_once()
    conn.unbind.assert_called_once()
