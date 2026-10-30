"""Passerelle SMS SENELEC — web service SOAP « OSPWebService ».

L'ancien SIR (WinDev) appelait ce web service importé depuis son WSDL. SIRV2 utilise
la méthode ``sendOneSignedSMS(numero, message, signature) -> string`` : un appel par
destinataire, avec la signature (nom d'expéditeur) affichée sur le téléphone.

Le WSDL est lu au premier envoi (adresse du service, espace de noms, SOAPAction,
version SOAP, noms des paramètres) puis gardé en mémoire. Configuration (.env) :

- ``SMS_GATEWAY_URL``       : adresse du serveur (http://10.101.2.86:8080) ou URL du WSDL ;
- ``SMS_GATEWAY_WSDL``      : URL exacte du WSDL si la recherche automatique échoue ;
- ``SMS_GATEWAY_SIGNATURE`` : signature des SMS (défaut « SENELEC »).
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from urllib.parse import urljoin
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

OPERATION = "sendOneSignedSMS"
PARAMS_PAR_DEFAUT = ("numero", "message", "signature")

NS_WSDL = "http://schemas.xmlsoap.org/wsdl/"
NS_XSD = "http://www.w3.org/2001/XMLSchema"
NS_SOAP11 = "http://schemas.xmlsoap.org/wsdl/soap/"
NS_SOAP12 = "http://schemas.xmlsoap.org/wsdl/soap12/"
ENV_SOAP11 = "http://schemas.xmlsoap.org/soap/envelope/"
ENV_SOAP12 = "http://www.w3.org/2003/05/soap-envelope"

# Emplacements usuels d'un WSDL quand seule l'adresse du serveur est connue
CHEMINS_WSDL = (
    "/OrangeSmsPro/OSPWebService?WSDL",
    "/OSPWebService?wsdl",
    "/OSPWebService/OSPWebService?wsdl",
    "/OSPWebService/services/OSPWebService?wsdl",
    "/services/OSPWebService?wsdl",
    "/OSPWebService.asmx?WSDL",
    "/?wsdl",
)

TIMEOUT = httpx.Timeout(30.0, connect=10.0)


class SmsGatewayError(RuntimeError):
    """Échec d'envoi : réseau, WSDL introuvable, faute SOAP ou réponse vide."""


@dataclass(frozen=True)
class ServiceSoap:
    wsdl_url: str
    endpoint: str
    namespace: str
    soap_action: str
    soap12: bool
    params: tuple[str, ...]
    params_qualifies: bool


_cache: ServiceSoap | None = None


def reinitialiser_cache() -> None:
    global _cache
    _cache = None


# ── Numéros ────────────────────────────────────────────────────────────────────


def normaliser_numero(numero: str) -> str:
    """Chiffres seuls, sans indicatif Sénégal : « +221 77 740 82 54 » → « 777408254 »
    (format du répertoire de l'ancien SIR)."""
    chiffres = re.sub(r"\D", "", numero or "")
    if chiffres.startswith("00221"):
        chiffres = chiffres[5:]
    elif chiffres.startswith("221") and len(chiffres) == 12:
        chiffres = chiffres[3:]
    return chiffres


# ── Lecture du WSDL ───────────────────────────────────────────────────────────


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _candidats_wsdl() -> list[str]:
    if settings.sms_gateway_wsdl:
        return [settings.sms_gateway_wsdl]
    base = settings.sms_gateway_url.strip()
    if not base:
        raise SmsGatewayError(
            "Passerelle SMS non configurée : SMS_GATEWAY_URL et SMS_GATEWAY_WSDL sont vides dans le conteneur "
            "(ajouter les lignes au fichier .env lu par docker compose, puis « docker compose up -d api worker »)"
        )
    if "wsdl" in base.lower():
        return [base]
    base = base.rstrip("/")
    return [base + chemin for chemin in CHEMINS_WSDL]


def analyser_wsdl(texte: str, wsdl_url: str, schemas_externes: dict[str, str] | None = None) -> ServiceSoap:
    """Extrait du WSDL ce qu'il faut pour appeler ``sendOneSignedSMS``."""
    racine = ET.fromstring(texte)
    namespace = racine.get("targetNamespace") or ""

    endpoint = ""
    soap12 = False
    for el in racine.iter():
        if _local(el.tag) == "address" and el.get("location"):
            ns = el.tag[1:].split("}")[0] if el.tag.startswith("{") else ""
            if ns in (NS_SOAP11, NS_SOAP12) and (not endpoint or ns == NS_SOAP11):
                endpoint, soap12 = el.get("location", ""), ns == NS_SOAP12
    if not endpoint:
        raise SmsGatewayError("WSDL sans adresse de service (soap:address)")

    soap_action = ""
    body_ns = ""
    for binding in racine.findall(f"{{{NS_WSDL}}}binding"):
        for op in binding.findall(f"{{{NS_WSDL}}}operation"):
            if op.get("name") != OPERATION:
                continue
            for el in op.iter():
                if _local(el.tag) == "operation" and el.get("soapAction") is not None:
                    soap_action = el.get("soapAction", "")
                if _local(el.tag) == "body" and el.get("namespace"):
                    body_ns = el.get("namespace", "")
    if not any(op.get("name") == OPERATION for op in racine.iter(f"{{{NS_WSDL}}}operation")):
        raise SmsGatewayError(f"Le WSDL ne propose pas la méthode {OPERATION}")

    # Paramètres : schéma en ligne ou importé (document/literal) ; sinon noms de l'ancien SIR
    params = PARAMS_PAR_DEFAUT
    qualifies = False
    schemas = list(racine.iter(f"{{{NS_XSD}}}schema"))
    for xsd in (schemas_externes or {}).values():
        schemas.append(ET.fromstring(xsd))
    for schema in schemas:
        for element in schema.findall(f"{{{NS_XSD}}}element"):
            if element.get("name") != OPERATION:
                continue
            noms = [e.get("name") for e in element.iter(f"{{{NS_XSD}}}element") if e is not element and e.get("name")]
            if not noms:
                # <element name="sendOneSignedSMS" type="tns:sendOneSignedSMS"/> : chercher le complexType
                type_nom = (element.get("type") or "").split(":")[-1]
                for ct in schema.findall(f"{{{NS_XSD}}}complexType"):
                    if ct.get("name") == type_nom:
                        noms = [e.get("name") for e in ct.iter(f"{{{NS_XSD}}}element") if e.get("name")]
            if len(noms) >= 3:
                params = tuple(noms[:3])
            qualifies = schema.get("elementFormDefault") == "qualified"
            if schema.get("targetNamespace"):
                namespace = schema.get("targetNamespace", namespace)

    return ServiceSoap(
        wsdl_url=wsdl_url,
        endpoint=endpoint,
        namespace=body_ns or namespace,
        soap_action=soap_action,
        soap12=soap12,
        params=params,
        params_qualifies=qualifies,
    )


def _imports_xsd(texte: str, wsdl_url: str) -> list[str]:
    racine = ET.fromstring(texte)
    return [
        urljoin(wsdl_url, imp.get("schemaLocation", ""))
        for imp in racine.iter(f"{{{NS_XSD}}}import")
        if imp.get("schemaLocation")
    ]


async def decouvrir_service(client: httpx.AsyncClient) -> ServiceSoap:
    global _cache
    if _cache is not None:
        return _cache
    erreurs: list[str] = []
    for url in _candidats_wsdl():
        try:
            rep = await client.get(url)
        except httpx.HTTPError as exc:
            erreurs.append(f"{url} : {exc.__class__.__name__}")
            continue
        if rep.status_code != 200 or "definitions" not in rep.text[:2000]:
            erreurs.append(f"{url} : HTTP {rep.status_code}")
            continue
        externes: dict[str, str] = {}
        for xsd_url in _imports_xsd(rep.text, url):
            try:
                r = await client.get(xsd_url)
                if r.status_code == 200:
                    externes[xsd_url] = r.text
            except httpx.HTTPError:
                logger.warning("Schéma XSD %s illisible : noms de paramètres par défaut", xsd_url)
        _cache = analyser_wsdl(rep.text, url, externes)
        logger.info("Passerelle SMS : WSDL %s → %s", url, _cache.endpoint)
        return _cache
    raise SmsGatewayError(
        "WSDL de la passerelle SMS introuvable ; renseigner SMS_GATEWAY_WSDL. Essais : " + " ; ".join(erreurs)
    )


# ── Appel SOAP ────────────────────────────────────────────────────────────────


def construire_enveloppe(service: ServiceSoap, *valeurs: str) -> str:
    """Enveloppe SOAP : ``valeurs`` dans l'ordre des paramètres (numéro, message, signature)."""
    env = ENV_SOAP12 if service.soap12 else ENV_SOAP11
    pfx = "ns:" if service.params_qualifies else ""
    corps = "".join(f"<{pfx}{nom}>{escape(val)}</{pfx}{nom}>" for nom, val in zip(service.params, valeurs, strict=False))
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<soap:Envelope xmlns:soap="{env}" xmlns:ns="{escape(service.namespace)}">'
        f"<soap:Body><ns:{OPERATION}>{corps}</ns:{OPERATION}></soap:Body></soap:Envelope>"
    )


def lire_reponse(texte: str) -> str:
    """Valeur renvoyée par le web service ; lève sur une faute SOAP."""
    try:
        racine = ET.fromstring(texte)
    except ET.ParseError as exc:
        raise SmsGatewayError(f"Réponse illisible de la passerelle : {texte[:200]}") from exc
    for el in racine.iter():
        if _local(el.tag) == "Fault":
            detail = " ".join(t.strip() for t in el.itertext() if t.strip())
            raise SmsGatewayError(f"Faute SOAP : {detail[:300]}")
    for el in racine.iter():
        if _local(el.tag) == f"{OPERATION}Response":
            enfants = list(el)
            valeur = "".join(enfants[0].itertext()) if enfants else "".join(el.itertext())
            return valeur.strip()
    return ""


async def envoyer_sms(numero: str, message: str) -> str:
    """Envoie ``message`` à ``numero`` par ``sendOneSignedSMS``.

    Retourne la réponse du web service. Lève ``SmsGatewayError`` si l'envoi échoue
    ou si la réponse est vide (« PAS DE REPONSE » dans l'ancien SIR).
    """
    num = normaliser_numero(numero)
    if not num:
        raise SmsGatewayError("Numéro invalide")
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        service = await decouvrir_service(client)
        enveloppe = construire_enveloppe(service, num, message, settings.sms_gateway_signature or "SENELEC")
        if service.soap12:
            headers = {"Content-Type": f'application/soap+xml; charset=utf-8; action="{service.soap_action}"'}
        else:
            headers = {"Content-Type": "text/xml; charset=utf-8", "SOAPAction": f'"{service.soap_action}"'}
        try:
            rep = await client.post(service.endpoint, content=enveloppe.encode("utf-8"), headers=headers)
        except httpx.HTTPError as exc:
            reinitialiser_cache()
            raise SmsGatewayError(f"Passerelle SMS injoignable : {exc.__class__.__name__}") from exc
    # Une faute SOAP arrive en HTTP 500 : lire le corps avant le code
    valeur = lire_reponse(rep.text) if rep.text else ""
    if rep.status_code >= 400:
        raise SmsGatewayError(f"HTTP {rep.status_code} : {rep.text[:200]}")
    if not valeur:
        raise SmsGatewayError("PAS DE REPONSE du web service")
    verifier_statut(valeur)
    return valeur


def verifier_statut(valeur: str) -> None:
    """Orange SMS Pro répond en JSON : ``status_CODE`` 200 = « Message envoye ».

    Lève ``SmsGatewayError`` avec ``status_TEXT`` si un destinataire est refusé.
    Une réponse non JSON est acceptée telle quelle.
    """
    try:
        donnees = json.loads(valeur)
        reponses = donnees["responses"]["response"]
    except (ValueError, KeyError, TypeError):
        return
    for rep in reponses if isinstance(reponses, list) else [reponses]:
        statut = (rep or {}).get("status") or {}
        code = str(statut.get("status_CODE", ""))
        if code and code != "200":
            raise SmsGatewayError(f"Refusé par Orange SMS Pro ({code}) : {statut.get('status_TEXT', '')}")
