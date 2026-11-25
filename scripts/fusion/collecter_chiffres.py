"""Collecte des chiffres de « Suivi incidents SIR » et de SIRV2 pour les comparer.

À lancer SOUS VPN SENELEC (Claude n'y a pas accès) : le script ne fait que des
lectures (GET) sur les deux API déployées, puis écrit les réponses brutes dans
un fichier JSON. Il n'utilise que la bibliothèque standard de Python.

    python scripts/fusion/collecter_chiffres.py

Les URL et les identifiants sont demandés au lancement ; le mot de passe est
saisi sans écho et n'est écrit nulle part (ni fichier, ni journal).
Le fichier produit (scripts/fusion/resultats_*.json) est ignoré par git.
"""

from __future__ import annotations

import getpass
import json
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime
from pathlib import Path
from typing import Any

ICI = Path(__file__).resolve().parent
ANNEE = 2026
MOIS = list(range(1, date.today().month + 1)) if date.today().year == ANNEE else list(range(1, 13))
TIMEOUT_S = 180  # les deux API peuvent être lentes au premier appel (cache froid)

# Certificats internes SENELEC : pas de vérification (lecture seule, réseau interne)
_SSL = ssl.create_default_context()
_SSL.check_hostname = False
_SSL.verify_mode = ssl.CERT_NONE


def _demander(question: str, defaut: str) -> str:
    rep = input(f"{question} [{defaut}] : ").strip()
    return rep or defaut


def _requete(methode: str, url: str, jeton: str | None = None, corps: dict[str, Any] | None = None) -> Any:
    donnees = json.dumps(corps).encode("utf-8") if corps is not None else None
    req = urllib.request.Request(url, data=donnees, method=methode)
    req.add_header("Accept", "application/json")
    if donnees is not None:
        req.add_header("Content-Type", "application/json")
    if jeton:
        req.add_header("Authorization", f"Bearer {jeton}")
    with urllib.request.urlopen(req, timeout=TIMEOUT_S, context=_SSL) as rep:
        return json.loads(rep.read().decode("utf-8"))


def _get(base: str, chemin: str, jeton: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """GET qui ne s'arrête jamais : renvoie la réponse ou l'erreur, pour garder le reste de la collecte."""
    url = base.rstrip("/") + chemin
    if params:
        url += "?" + urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    try:
        return {"url": url, "ok": True, "reponse": _requete("GET", url, jeton)}
    except urllib.error.HTTPError as e:
        return {"url": url, "ok": False, "erreur": f"HTTP {e.code}", "detail": e.read().decode("utf-8", "replace")[:500]}
    except Exception as e:  # noqa: BLE001 — on consigne et on continue
        return {"url": url, "ok": False, "erreur": type(e).__name__, "detail": str(e)[:500]}
    finally:
        print(f"  · {chemin} {params or ''}", flush=True)


def _bornes(mois: int) -> tuple[str, str]:
    fin = date(ANNEE + (mois == 12), mois % 12 + 1, 1)
    dernier = date.fromordinal(fin.toordinal() - 1)
    return date(ANNEE, mois, 1).isoformat(), dernier.isoformat()


def collecter_suivi(base: str, jeton: str) -> dict[str, Any]:
    out: dict[str, Any] = {"synthese": _get(base, "/api/stats/saifi_synthese", jeton)}
    for zone in ("dakar", "regions"):
        z: dict[str, Any] = {
            "mensuel": _get(base, "/api/stats/saifi_saidi_mensuel", jeton,
                            {"date_debut": f"{ANNEE}-01-01", "date_fin": date.today().isoformat(), "zone": zone}),
            "mois": {},
        }
        for m in MOIS:
            debut, fin = _bornes(m)
            p = {"date_debut": debut, "date_fin": fin, "zone": zone}
            z["mois"][f"{ANNEE}-{m:02d}"] = {
                "kpi": _get(base, "/api/stats/kpi", jeton, p),
                "detail": _get(base, "/api/stats/saifi_saidi_detail", jeton, p),
                "nature": _get(base, "/api/stats/by_nature", jeton, p),
            }
        out[zone] = z
    return out


def collecter_sirv2(base: str, jeton: str) -> dict[str, Any]:
    api = "/api/v1"
    out: dict[str, Any] = {"regions": _get(base, f"{api}/geo/regions", jeton)}
    regions: list[dict[str, Any]] = []
    rep = out["regions"].get("reponse") or {}
    data = rep.get("data") if isinstance(rep, dict) else rep
    if isinstance(data, dict):
        data = data.get("items", [])
    if isinstance(data, list):
        regions = [r for r in data if isinstance(r, dict) and "id" in r]

    perimetres: list[tuple[str, int | None]] = [("national", None)] + [
        (str(r.get("libelle") or r.get("nom") or r["id"]), int(r["id"])) for r in regions
    ]
    for nom, region_id in perimetres:
        p: dict[str, Any] = {"region_id": region_id}
        bloc: dict[str, Any] = {
            "region_id": region_id,
            "synthese": _get(base, f"{api}/indicateurs/synthese-saifi-saidi", jeton, p),
            "historique": {
                t: _get(base, f"{api}/indicateurs/historique", jeton,
                        {**p, "type": t, "annees": 1, "fin": f"{ANNEE}-{MOIS[-1]:02d}"})
                for t in ("saifi", "saidi", "end")
            },
            "mois": {
                f"{ANNEE}-{m:02d}": _get(base, f"{api}/indicateurs/tableau-de-bord", jeton,
                                         {**p, "periode": f"{ANNEE}-{m:02d}"})
                for m in MOIS
            },
        }
        out[nom] = bloc
    return out


def _connexion(nom: str, url: str, chemin: str, champ_login: str) -> str | None:
    login = input(f"Identifiant {nom} (Windows) : ").strip()
    mdp = getpass.getpass(f"Mot de passe {nom} : ")
    try:
        rep = _requete("POST", url.rstrip("/") + chemin, corps={champ_login: login, "password": mdp})
    except urllib.error.HTTPError as e:
        print(f"  ✗ Connexion {nom} refusée (HTTP {e.code})")
        return None
    except Exception as e:  # noqa: BLE001
        print(f"  ✗ {nom} injoignable : {e}")
        return None
    finally:
        del mdp
    jeton = rep.get("access_token") or (rep.get("data") or {}).get("access_token")
    if not jeton:
        print(f"  ✗ Réponse de connexion {nom} sans jeton")
    return jeton


def main() -> int:
    sys.stdout.reconfigure(errors="replace")  # console Windows non UTF-8 : jamais d'arrêt sur un caractère
    print("Collecte des chiffres Suivi incidents / SIRV2 — lecture seule\n")
    url_suivi = _demander("URL de Suivi incidents", "http://srv-applisnlcprod:8070")
    url_sirv2 = _demander("URL de SIRV2", "http://srv-applisnlcprod:4210")

    resultat: dict[str, Any] = {
        "date_collecte": datetime.now().isoformat(timespec="seconds"),
        "annee": ANNEE,
        "mois": MOIS,
        "suivi_incidents": {"url": url_suivi},
        "sirv2": {"url": url_sirv2},
    }

    jeton = _connexion("Suivi incidents", url_suivi, "/api/auth/login", "username")
    if jeton:
        print("Suivi incidents : collecte…")
        resultat["suivi_incidents"].update(collecter_suivi(url_suivi, jeton))

    jeton = _connexion("SIRV2", url_sirv2, "/api/v1/auth/login", "login")
    if jeton:
        print("SIRV2 : collecte…")
        resultat["sirv2"].update(collecter_sirv2(url_sirv2, jeton))

    fichier = ICI / f"resultats_{datetime.now():%Y%m%d_%H%M}.json"
    fichier.write_text(json.dumps(resultat, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nTerminé : {fichier}")
    print("Déconnecte le VPN puis préviens Claude.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
