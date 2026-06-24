#!/usr/bin/env python3
"""Diagnostic périmètre bcc.dev / brc.dev vs données migrées."""

import asyncio

from sqlalchemy import text

from app.core.database import AsyncSessionLocal


async def main() -> None:
    async with AsyncSessionLocal() as db:
        total = (await db.execute(text(
            "SELECT COUNT(*) FROM dbo.interruptions WHERE type_direction = 'distribution'"
        ))).scalar()
        print(f"Interruptions distribution : {total}")

        print("\n--- Comptes dev ---")
        rows = (await db.execute(text("""
            SELECT u.login, r.nom, ur.scope_service_id
            FROM dbo.utilisateurs u
            JOIN dbo.user_roles ur ON ur.utilisateur_id = u.id
            JOIN dbo.roles r ON r.id = ur.role_id
            WHERE u.login IN ('bcc.dev', 'brc.dev')
        """))).all()
        for row in rows:
            print(row)

        print("\n--- Top régions (interruptions) ---")
        rows = (await db.execute(text("""
            SELECT TOP 5 reg.id, reg.libelle, COUNT(*) AS cnt
            FROM dbo.interruptions i
            JOIN dbo.services s ON s.id = i.service_id
            JOIN dbo.agences a ON a.id = s.agence_id
            JOIN dbo.delegations d ON d.id = a.delegation_id
            JOIN dbo.regions reg ON reg.id = d.region_id
            WHERE i.type_direction = 'distribution'
            GROUP BY reg.id, reg.libelle
            ORDER BY cnt DESC
        """))).all()
        for row in rows:
            print(row)

        print("\n--- Top services (interruptions) ---")
        rows = (await db.execute(text("""
            SELECT TOP 5 i.service_id, s.libelle, COUNT(*) AS cnt
            FROM dbo.interruptions i
            LEFT JOIN dbo.services s ON s.id = i.service_id
            WHERE i.type_direction = 'distribution'
            GROUP BY i.service_id, s.libelle
            ORDER BY cnt DESC
        """))).all()
        for row in rows:
            print(row)

        print("\n--- Interruptions visibles bcc.dev (service_id=1) ---")
        bcc_cnt = (await db.execute(text(
            "SELECT COUNT(*) FROM dbo.interruptions WHERE type_direction='distribution' AND service_id = 1"
        ))).scalar()
        print(bcc_cnt)

        print("\n--- Interruptions visibles brc.dev (region_id=1) ---")
        brc_cnt = (await db.execute(text("""
            SELECT COUNT(*)
            FROM dbo.interruptions i
            JOIN dbo.services s ON s.id = i.service_id
            JOIN dbo.agences a ON a.id = s.agence_id
            JOIN dbo.delegations d ON d.id = a.delegation_id
            WHERE i.type_direction = 'distribution' AND d.region_id = 1
        """))).scalar()
        print(brc_cnt)

        print("\n--- Service id=1 / Region id=1 ---")
        svc = (await db.execute(text("SELECT id, code, libelle FROM dbo.services WHERE id = 1"))).first()
        reg = (await db.execute(text("SELECT id, code, libelle FROM dbo.regions WHERE id = 1"))).first()
        print("service:", svc)
        print("region:", reg)


if __name__ == "__main__":
    asyncio.run(main())
