import asyncio
from sqlalchemy import text
from app.core.database import AsyncSessionLocal

async def main() -> None:
    async with AsyncSessionLocal() as db:
        rows = (
            await db.execute(
                text(
                    "SELECT TOP 8 u.login, r.nom FROM utilisateurs u "
                    "JOIN user_roles ur ON ur.utilisateur_id = u.id "
                    "JOIN roles r ON r.id = ur.role_id "
                    "WHERE u.is_active = 1 ORDER BY u.id"
                )
            )
        ).all()
        for login, role in rows:
            print(f"{login} ({role})")

asyncio.run(main())
