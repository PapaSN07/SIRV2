"""Connexion LDAP / Active Directory (compte de service SENELEC)."""

from __future__ import annotations

import logging
import ssl
from dataclasses import dataclass

from ldap3 import ALL, FIRST, SUBTREE, Connection, Server, ServerPool, Tls
from ldap3.core.exceptions import LDAPException
from ldap3.utils.conv import escape_filter_chars

from app.core.config import settings

logger = logging.getLogger(__name__)
_plaintext_warned = False

# Attributs AD utiles pour un diagnostic (jamais de mot de passe).
_USER_ATTRIBUTES = (
    "distinguishedName",
    "sAMAccountName",
    "userPrincipalName",
    "displayName",
    "mail",
    "cn",
)


@dataclass(frozen=True, slots=True)
class LdapUser:
    dn: str
    sam_account_name: str | None
    user_principal_name: str | None
    display_name: str | None
    mail: str | None


class LdapConfigurationError(RuntimeError):
    """LDAP activé mais paramètres incomplets."""


class LdapBindError(RuntimeError):
    """Échec de bind du compte de service (hôte injoignable ou identifiants)."""


def _strip_quotes(value: str) -> str:
    text = value.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {"'", '"'}:
        return text[1:-1]
    return text


def _tls() -> Tls | None:
    """Configuration TLS (certificat serveur vérifié) si LDAPS ou StartTLS est activé."""
    if not (settings.ldap_use_ssl or settings.ldap_start_tls):
        return None
    return Tls(
        validate=ssl.CERT_REQUIRED,
        ca_certs_file=settings.ldap_ca_cert_file or None,
    )


def _warn_if_plaintext() -> None:
    global _plaintext_warned
    if not _plaintext_warned and not (settings.ldap_use_ssl or settings.ldap_start_tls):
        logger.warning(
            "LDAP sans chiffrement : les mots de passe circulent en clair. "
            "Activer LDAP_START_TLS=true (port 389) ou LDAP_USE_SSL=true (port 636)."
        )
        _plaintext_warned = True


def _server_pool() -> ServerPool:
    tls = _tls()
    servers = [
        Server(
            host,
            port=settings.ldap_port,
            use_ssl=settings.ldap_use_ssl,
            tls=tls,
            get_info=ALL,
            connect_timeout=settings.ldap_timeout_seconds,
        )
        for host in settings.ldap_hosts_list
    ]
    return ServerPool(servers, pool_strategy=FIRST, active=True, exhaust=True)


def _bind(conn: Connection) -> bool:
    """Ouvre la connexion, passe en StartTLS si configuré, puis bind."""
    _warn_if_plaintext()
    if settings.ldap_start_tls and not settings.ldap_use_ssl:
        conn.open()
        if not conn.start_tls():
            return False
    return bool(conn.bind())


def _service_connection(*, read_only: bool = True) -> Connection:
    if not settings.ldap_is_configured:
        raise LdapConfigurationError(
            "LDAP non configuré (LDAP_ENABLED, LDAP_HOSTS, LDAP_BIND_DN, LDAP_BIND_PASSWORD)"
        )
    conn = Connection(
        _server_pool(),
        user=_strip_quotes(settings.ldap_bind_dn),
        password=settings.ldap_bind_password,
        auto_bind=False,
        auto_referrals=False,
        read_only=read_only,
        receive_timeout=settings.ldap_timeout_seconds,
    )
    if not _bind(conn):
        raise LdapBindError(conn.result.get("description", "bind LDAP échoué"))
    return conn


def bind_service_account() -> str:
    """Bind le compte de service et retourne le serveur réellement utilisé."""
    conn = _service_connection()
    try:
        server = getattr(conn.server, "host", None) or str(conn.server)
        return str(server)
    finally:
        conn.unbind()


def search_user_by_login(login: str) -> LdapUser | None:
    """Recherche un compte AD par sAMAccountName via le bind service.sip."""
    login_clean = login.strip()
    if not login_clean:
        return None
    filt = settings.ldap_user_search_filter.format(login=escape_filter_chars(login_clean))
    conn = _service_connection()
    try:
        found = conn.search(
            search_base=_strip_quotes(settings.ldap_base_dn),
            search_filter=filt,
            search_scope=SUBTREE,
            attributes=list(_USER_ATTRIBUTES),
            size_limit=1,
        )
        if not found or not conn.entries:
            return None
        entry = conn.entries[0]
        attrs = entry.entry_attributes_as_dict
        return LdapUser(
            dn=str(entry.entry_dn),
            sam_account_name=_first_str(attrs.get("sAMAccountName")),
            user_principal_name=_first_str(attrs.get("userPrincipalName")),
            display_name=_first_str(attrs.get("displayName")),
            mail=_first_str(attrs.get("mail")),
        )
    except LDAPException as exc:
        raise LdapBindError(str(exc)) from exc
    finally:
        conn.unbind()


def verify_user_password(login: str, password: str) -> bool | None:
    """Vérifie le mot de passe Active Directory de l'utilisateur.

    Retourne True si le bind utilisateur réussit, False si le compte AD existe
    mais le mot de passe est refusé, None si LDAP est inactif, le compte est
    absent de l'annuaire, ou l'annuaire est injoignable (repli mot de passe local).
    """
    if not settings.ldap_is_configured or not login.strip() or not password:
        return None
    try:
        user = search_user_by_login(login)
    except (LdapBindError, LdapConfigurationError, LDAPException):
        return None
    if user is None:
        return None

    conn = Connection(
        _server_pool(),
        user=user.dn,
        password=password,
        auto_bind=False,
        auto_referrals=False,
        read_only=True,
        receive_timeout=settings.ldap_timeout_seconds,
    )
    try:
        return _bind(conn)
    except LDAPException:
        return False
    finally:
        try:
            conn.unbind()
        except LDAPException:
            pass


def _first_str(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, list):
        if not value:
            return None
        return str(value[0])
    text = str(value).strip()
    return text or None
