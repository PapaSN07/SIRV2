"""Transfère les tables du schéma db_owner (ou autre) vers dbo sur SIRV2."""
import pyodbc

CS = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=srv-bddomtech;DATABASE=SIRV2;"
    "UID=LectSIP;PWD=LectSIP;TrustServerCertificate=yes"
)

SOURCE_SCHEMAS = ("db_owner",)  # schéma où Alembic a créé les tables


def main() -> None:
    conn = pyodbc.connect(CS, timeout=30)
    conn.autocommit = True
    cur = conn.cursor()

    for source in SOURCE_SCHEMAS:
        cur.execute(
            """
            SELECT t.name
            FROM sys.tables t
            JOIN sys.schemas s ON t.schema_id = s.schema_id
            WHERE s.name = ?
            ORDER BY t.name
            """,
            (source,),
        )
        tables = [r[0] for r in cur.fetchall()]
        if not tables:
            print(f"Schéma {source} : aucune table")
            continue

        print(f"Schéma {source} : {len(tables)} table(s) à transférer vers dbo")
        pending = list(tables)
        moved: set[str] = set()

        for attempt in range(1, 6):
            still_pending: list[str] = []
            for table in pending:
                sql = f"ALTER SCHEMA dbo TRANSFER [{source}].[{table}]"
                try:
                    cur.execute(sql)
                    moved.add(table)
                    print(f"  OK  {source}.{table} -> dbo.{table}")
                except pyodbc.Error as e:
                    still_pending.append(table)
                    if attempt == 5:
                        print(f"  ERR {source}.{table}: {e.args[1][:100] if e.args else e}")
        if not still_pending:
            pending = []
            break
        pending = still_pending
            print(f"  Passe {attempt} : {len(still_pending)} table(s) en attente, nouvel essai...")

        if pending:
            print(f"ECHEC : {len(pending)} table(s) non transférée(s): {pending}")
        else:
            print(f"OK : {len(moved)} table(s) dans dbo")

    # Schéma par défaut
    try:
        cur.execute("ALTER USER LectSIP WITH DEFAULT_SCHEMA = dbo")
        print("Default schema LectSIP -> dbo")
    except pyodbc.Error as e:
        print(f"ALTER USER (nécessite DBA?) : {e.args[1][:100] if e.args else e}")

    cur.execute(
        """
        SELECT s.name, COUNT(*)
        FROM sys.tables t JOIN sys.schemas s ON t.schema_id = s.schema_id
        WHERE s.name NOT IN ('sys')
        GROUP BY s.name
        """
    )
    print("\nÉtat final :")
    for schema, cnt in cur.fetchall():
        print(f"  {schema}: {cnt} table(s)")

    conn.close()


if __name__ == "__main__":
    main()
