"""Test de la passerelle SMS SENELEC (OSPWebService.sendManySMS).

Usage (dans le conteneur api) :
    python -m scripts.test_sms                      # lit le WSDL et affiche ce qui a été trouvé
    python -m scripts.test_sms 77XXXXXXX 78XXXXXXX  # envoie un SMS de test à ces numéros
"""

import asyncio
import sys

import httpx

from app.core.config import settings
from app.services import sms_gateway


async def main(numeros: list[str]) -> int:
    print(f"SMS_GATEWAY_URL  = {settings.sms_gateway_url or '(vide)'}")
    print(f"SMS_GATEWAY_WSDL = {settings.sms_gateway_wsdl or '(recherche automatique)'}")
    try:
        async with httpx.AsyncClient(timeout=sms_gateway.TIMEOUT) as client:
            service = await sms_gateway.decouvrir_service(client)
    except sms_gateway.SmsGatewayError as exc:
        print(f"ÉCHEC : {exc}")
        return 1
    print(f"WSDL        : {service.wsdl_url}")
    print(f"Adresse     : {service.endpoint}")
    print(f"Namespace   : {service.namespace}")
    print(f"SOAP        : {'1.2' if service.soap12 else '1.1'} · SOAPAction « {service.soap_action} »")
    print(f"Paramètres  : {service.params} (qualifiés : {service.params_qualifies})")
    if not numeros:
        return 0
    try:
        retour = await sms_gateway.envoyer_lot(numeros, "Test SIRV2 : passerelle SMS opérationnelle.")
    except sms_gateway.SmsGatewayError as exc:
        print(f"ENVOI EN ÉCHEC : {exc}")
        return 1
    print(f"Réponse de sendManySMS : {retour}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
