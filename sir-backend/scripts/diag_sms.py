"""Derniers SMS envoyés à un numéro : statut, code Orange, identifiant de message (lecture seule).

« envoye » sans code_retour ni message_id : le SMS n'a pas été transmis à Orange (passerelle
non configurée avant le correctif du 04/11/2026). Code 200 + message_id : accepté par Orange.

Usage :
    docker compose exec api python -m scripts.diag_sms 77XXXXXXX
    docker compose exec api python -m scripts.diag_sms 77XXXXXXX --nombre 50
"""

from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import text

from app.core.config import settings
from app.core.database import AsyncSessionLocal, engine
from app.services.sms_gateway import normaliser_numero

_SQL = """
SELECT TOP (:n) s.id, s.created_at, s.sent_at, s.statut, s.code_retour, s.message_id, s.erreur,
       d.telephone, s.entity_type, CAST(s.contenu AS NVARCHAR(200)) AS contenu
FROM dbo.sms_envoyes s
JOIN dbo.destinataires d ON d.id = s.destinataire_id
WHERE d.telephone LIKE :numero
ORDER BY s.created_at DESC
"""


async def main(numero: str, nombre: int) -> None:
    engine.echo = False
    num = normaliser_numero(numero)
    print(
        f"Passerelle : URL={'oui' if settings.sms_gateway_url else 'vide'} · WSDL={'oui' if settings.sms_gateway_wsdl else 'vide'}"
    )
    async with AsyncSessionLocal() as db:
        lignes = (await db.execute(text(_SQL), {"n": nombre, "numero": f"%{num[-9:]}%"})).all()
    await engine.dispose()
    if not lignes:
        print(f"Aucun SMS pour un destinataire dont le numéro contient {num[-9:]}")
        return
    for i, cree, envoye, statut, code, mid, erreur, tel, etype, contenu in lignes:
        if statut == "envoye" and not code and not mid:
            verdict = "NON TRANSMIS à Orange (marqué envoyé à tort)"
        elif statut == "envoye":
            verdict = f"accepté par Orange (code {code or '?'}, message {mid or '?'})"
        else:
            verdict = f"{statut} : {erreur or ''}"
        print(f"#{i} {cree:%d/%m %H:%M} → {tel} [{etype}] {verdict}")
        print(f"     « {(contenu or '')[:70]} »")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("numero")
    parser.add_argument("--nombre", type=int, default=30)
    args = parser.parse_args()
    asyncio.run(main(args.numero, args.nombre))
