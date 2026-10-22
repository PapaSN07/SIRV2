"""Teste le bind LDAP du compte de service SENELEC.

Usage (bureau SENELEC) :
    cd sir-backend
    $env:SIR_PROFILE = "senelec"
    python scripts/test_ldap.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

os.environ.setdefault("SIR_PROFILE", "senelec")

from app.core.config import settings  # noqa: E402
from app.services.ldap_service import (  # noqa: E402
    LdapBindError,
    LdapConfigurationError,
    bind_service_account,
    search_user_by_login,
)


def main() -> int:
    print("LDAP_ENABLED =", settings.ldap_enabled)
    print("LDAP_HOSTS   =", ", ".join(settings.ldap_hosts_list))
    print("LDAP_PORT    =", settings.ldap_port)
    print("LDAP_BIND_DN =", settings.ldap_bind_dn)
    print("LDAP_BASE_DN =", settings.ldap_base_dn)
    print("LDAP_SSL     =", settings.ldap_use_ssl)
    if not settings.ldap_is_configured:
        print("LDAP incomplet — renseigner LDAP_* dans .env.senelec")
        return 2
    try:
        host = bind_service_account()
        print("Bind compte de service : OK")
        print("Serveur utilisé        :", host)
        account = search_user_by_login("service.sip")
        if account is None:
            print("Recherche sAMAccountName=service.sip : aucun résultat")
            return 1
        print("Compte trouvé          :", account.dn)
        print("sAMAccountName         :", account.sam_account_name)
        print("UPN                    :", account.user_principal_name)
        print("Nom affiché            :", account.display_name)
        return 0
    except (LdapConfigurationError, LdapBindError) as exc:
        print("Échec LDAP :", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
