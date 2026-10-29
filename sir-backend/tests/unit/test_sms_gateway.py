"""Passerelle SMS SOAP (OSPWebService.sendManySMS) : WSDL, enveloppe, réponse, lots."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.services import sms_gateway, sms_service

WSDL = """<?xml version="1.0"?>
<definitions xmlns="http://schemas.xmlsoap.org/wsdl/" xmlns:soap="http://schemas.xmlsoap.org/wsdl/soap/"
  xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:tns="http://ws.osp.sn/" targetNamespace="http://ws.osp.sn/" name="OSPWebService">
  <types>
    <xsd:schema targetNamespace="http://ws.osp.sn/">
      <xsd:element name="sendManySMS" type="tns:sendManySMS"/>
      <xsd:complexType name="sendManySMS"><xsd:sequence>
        <xsd:element name="listOfNums" type="xsd:string"/><xsd:element name="message" type="xsd:string"/>
      </xsd:sequence></xsd:complexType>
    </xsd:schema>
  </types>
  <portType name="OSP"><operation name="sendManySMS"/><operation name="sendOneSMS"/></portType>
  <binding name="OSPBinding" type="tns:OSP">
    <soap:binding style="document" transport="http://schemas.xmlsoap.org/soap/http"/>
    <operation name="sendManySMS"><soap:operation soapAction=""/></operation>
  </binding>
  <service name="OSPWebService"><port name="OSPPort" binding="tns:OSPBinding">
    <soap:address location="http://10.101.2.86:8080/OSPWebService/OSPWebService"/>
  </port></service>
</definitions>"""

REPONSE = """<S:Envelope xmlns:S="http://schemas.xmlsoap.org/soap/envelope/"><S:Body>
<ns2:sendManySMSResponse xmlns:ns2="http://ws.osp.sn/"><return>OK:2</return></ns2:sendManySMSResponse>
</S:Body></S:Envelope>"""

FAUTE = """<S:Envelope xmlns:S="http://schemas.xmlsoap.org/soap/envelope/"><S:Body><S:Fault>
<faultcode>S:Server</faultcode><faultstring>numero invalide</faultstring></S:Fault></S:Body></S:Envelope>"""


def test_normaliser_numero() -> None:
    assert sms_gateway.normaliser_numero("+221 77 740 82 54") == "777408254"
    assert sms_gateway.normaliser_numero("00221777408254") == "777408254"
    assert sms_gateway.normaliser_numero("77-740-82-54") == "777408254"


def test_analyser_wsdl_et_enveloppe() -> None:
    service = sms_gateway.analyser_wsdl(WSDL, "http://x/OSPWebService?wsdl")
    assert service.endpoint == "http://10.101.2.86:8080/OSPWebService/OSPWebService"
    assert service.namespace == "http://ws.osp.sn/"
    assert service.params == ("listOfNums", "message") and not service.soap12
    env = sms_gateway.construire_enveloppe(service, "771111111,772222222", "Coupure HANN & Médina")
    assert "<ns:sendManySMS><listOfNums>771111111,772222222</listOfNums>" in env
    assert "Coupure HANN &amp; Médina" in env


def test_lire_reponse() -> None:
    assert sms_gateway.lire_reponse(REPONSE) == "OK:2"
    with pytest.raises(sms_gateway.SmsGatewayError, match="numero invalide"):
        sms_gateway.lire_reponse(FAUTE)


@pytest.mark.asyncio
async def test_envoyer_lot_decouvre_le_wsdl(monkeypatch) -> None:
    appels: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        appels.append(request)
        if request.method == "GET":
            if request.url.path == "/OSPWebService/OSPWebService":
                return httpx.Response(200, text=WSDL)
            return httpx.Response(404)
        return httpx.Response(200, text=REPONSE)

    vrai_client = httpx.AsyncClient
    monkeypatch.setattr(sms_gateway.httpx, "AsyncClient", lambda **kw: vrai_client(transport=httpx.MockTransport(handler)))
    monkeypatch.setattr(sms_gateway.settings, "sms_gateway_url", "http://10.101.2.86:8080")
    monkeypatch.setattr(sms_gateway.settings, "sms_gateway_wsdl", "")
    monkeypatch.setattr(sms_gateway.settings, "sms_gateway_separateur", ",")
    sms_gateway.reinitialiser_cache()

    retour = await sms_gateway.envoyer_lot(["+221771111111", "77 222 22 22"], "Test")
    assert retour == "OK:2"
    post = appels[-1]
    assert post.method == "POST" and post.headers["SOAPAction"] == '""'
    assert b"<listOfNums>771111111,772222222</listOfNums>" in post.content
    sms_gateway.reinitialiser_cache()


@pytest.mark.asyncio
async def test_send_sms_lot_regroupe_par_message(monkeypatch) -> None:
    monkeypatch.setattr(sms_service.settings, "sms_gateway_url", "http://10.101.2.86:8080")

    def rec(i: int, tel: str | None, contenu: str = "Coupure") -> MagicMock:
        r = MagicMock(id=i, contenu=contenu)
        r.destinataire = MagicMock(telephone=tel)
        return r

    records = {1: rec(1, "771111111"), 2: rec(2, "772222222"), 3: rec(3, None), 4: rec(4, "773333333", "Autre")}
    envoyer = AsyncMock(return_value="OK")
    with patch("app.services.sms_service.repo.get_by_id", new=AsyncMock(side_effect=lambda db, i: records[i])), patch(
        "app.services.sms_service.repo.update_statut", new=AsyncMock()
    ) as maj, patch("app.services.sms_service.sms_gateway.envoyer_lot", new=envoyer):
        resultat = await sms_service.send_sms_lot(AsyncMock(), [1, 2, 3, 4])

    assert resultat == {"envoyes": 3, "echecs": 1}
    assert envoyer.await_count == 2
    envoyer.assert_any_await(["771111111", "772222222"], "Coupure")
    assert maj.await_count == 4
