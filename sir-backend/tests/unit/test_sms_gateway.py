"""Passerelle SMS SOAP (OSPWebService.sendOneSignedSMS) : WSDL, enveloppe, réponse, envois."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.services import sms_gateway, sms_service

WSDL = """<?xml version="1.0"?>
<definitions xmlns="http://schemas.xmlsoap.org/wsdl/" xmlns:soap="http://schemas.xmlsoap.org/wsdl/soap/"
  xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:tns="http://ws.osp.sn/" targetNamespace="http://ws.osp.sn/" name="OSPWebService">
  <types>
    <xsd:schema targetNamespace="http://ws.osp.sn/">
      <xsd:element name="sendOneSignedSMS" type="tns:sendOneSignedSMS"/>
      <xsd:complexType name="sendOneSignedSMS"><xsd:sequence>
        <xsd:element name="numero" type="xsd:string"/><xsd:element name="message" type="xsd:string"/>
        <xsd:element name="signature" type="xsd:string"/>
      </xsd:sequence></xsd:complexType>
    </xsd:schema>
  </types>
  <portType name="OSP"><operation name="sendManySMS"/><operation name="sendOneSignedSMS"/></portType>
  <binding name="OSPBinding" type="tns:OSP">
    <soap:binding style="document" transport="http://schemas.xmlsoap.org/soap/http"/>
    <operation name="sendOneSignedSMS"><soap:operation soapAction=""/></operation>
  </binding>
  <service name="OSPWebService"><port name="OSPPort" binding="tns:OSPBinding">
    <soap:address location="http://10.101.2.86:8080/OSPWebService/OSPWebService"/>
  </port></service>
</definitions>"""

REPONSE = """<S:Envelope xmlns:S="http://schemas.xmlsoap.org/soap/envelope/"><S:Body>
<ns2:sendOneSignedSMSResponse xmlns:ns2="http://ws.osp.sn/"><return>OK</return></ns2:sendOneSignedSMSResponse>
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
    assert service.params == ("numero", "message", "signature") and not service.soap12
    env = sms_gateway.construire_enveloppe(service, "771111111", "Coupure HANN & Médina", "SENELEC")
    assert "<ns:sendOneSignedSMS><numero>771111111</numero>" in env
    assert "<signature>SENELEC</signature></ns:sendOneSignedSMS>" in env
    assert "Coupure HANN &amp; Médina" in env


def test_lire_reponse() -> None:
    assert sms_gateway.lire_reponse(REPONSE) == "OK"
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
    monkeypatch.setattr(sms_gateway.settings, "sms_gateway_signature", "SENELEC")
    sms_gateway.reinitialiser_cache()

    retour = await sms_gateway.envoyer_sms("+221 77 111 11 11", "Test")
    assert retour == "OK"
    post = appels[-1]
    assert post.method == "POST" and post.headers["SOAPAction"] == '""'
    assert b"<numero>771111111</numero><message>Test</message><signature>SENELEC</signature>" in post.content
    sms_gateway.reinitialiser_cache()


@pytest.mark.asyncio
async def test_send_sms_lot_un_appel_par_destinataire(monkeypatch) -> None:
    monkeypatch.setattr(sms_service.settings, "sms_gateway_url", "http://10.101.2.86:8080")

    def rec(i: int, tel: str | None) -> MagicMock:
        r = MagicMock(id=i, contenu="Coupure")
        r.destinataire = MagicMock(telephone=tel)
        return r

    records = {1: rec(1, "771111111"), 2: rec(2, "772222222"), 3: rec(3, None)}
    envoyer = AsyncMock(side_effect=["OK", sms_gateway.SmsGatewayError("Faute SOAP : numero invalide")])
    with patch("app.services.sms_service.repo.get_by_id", new=AsyncMock(side_effect=lambda db, i: records[i])), patch(
        "app.services.sms_service.repo.update_statut", new=AsyncMock()
    ) as maj, patch("app.services.sms_service.sms_gateway.envoyer_sms", new=envoyer):
        with pytest.raises(sms_gateway.SmsGatewayError):
            await sms_service.send_sms_lot(AsyncMock(), [1, 2, 3])

    assert envoyer.await_count == 2
    envoyer.assert_any_await("771111111", "Coupure")
    statuts = [c.kwargs["statut"] for c in maj.await_args_list]
    assert statuts == ["envoye", "echec", "echec"]
