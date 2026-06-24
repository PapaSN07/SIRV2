-- Déplace les tables SIRV2 vers le schéma dbo.
-- Cas fréquent SENELEC : tables créées dans db_owner (schéma par défaut du login LectSIP).
--
-- Prérequis DBA (une fois) :
--   USE SIRV2;
--   ALTER USER LectSIP WITH DEFAULT_SCHEMA = dbo;
--
-- Usage :
--   sqlcmd -S srv-bddomtech -d SIRV2 -U LectSIP -P LectSIP -i move_tables_to_dbo.sql
--
-- Alternative Python (plus robuste, plusieurs passes) :
--   python scripts/move_tables_to_dbo.py

SET NOCOUNT ON;

DECLARE @source_schema sysname;
DECLARE @table_name sysname;
DECLARE @sql nvarchar(500);
DECLARE @moved int = 0;
DECLARE @attempt int = 0;
DECLARE @remaining int = 1;

-- Schéma source : celui qui contient le plus de tables hors dbo
SELECT TOP 1 @source_schema = s.name
FROM sys.tables t
INNER JOIN sys.schemas s ON t.schema_id = s.schema_id
WHERE s.name <> 'dbo'
  AND s.name NOT IN ('sys', 'guest', 'INFORMATION_SCHEMA')
GROUP BY s.name
ORDER BY COUNT(*) DESC;

IF @source_schema IS NULL
BEGIN
    PRINT 'Rien à migrer — toutes les tables sont déjà dans dbo.';
    RETURN;
END;

PRINT 'Schéma source : ' + @source_schema;
PRINT 'Transfert vers dbo...';

WHILE @attempt < 5 AND @remaining > 0
BEGIN
    SET @attempt = @attempt + 1;
    SET @remaining = 0;

    DECLARE table_cursor CURSOR LOCAL FAST_FORWARD FOR
        SELECT t.name
        FROM sys.tables t
        INNER JOIN sys.schemas s ON t.schema_id = s.schema_id
        WHERE s.name = @source_schema
        ORDER BY t.name;

    OPEN table_cursor;
    FETCH NEXT FROM table_cursor INTO @table_name;

    WHILE @@FETCH_STATUS = 0
    BEGIN
        SET @sql = N'ALTER SCHEMA dbo TRANSFER ' + QUOTENAME(@source_schema) + N'.' + QUOTENAME(@table_name);
        BEGIN TRY
            EXEC sp_executesql @sql;
            SET @moved = @moved + 1;
            PRINT '  OK  ' + @source_schema + '.' + @table_name;
        END TRY
        BEGIN CATCH
            SET @remaining = @remaining + 1;
            IF @attempt = 5
                PRINT '  ERR ' + @table_name + ' : ' + ERROR_MESSAGE();
        END CATCH;

        FETCH NEXT FROM table_cursor INTO @table_name;
    END;

    CLOSE table_cursor;
    DEALLOCATE table_cursor;

    IF @remaining > 0
        PRINT '  Passe ' + CAST(@attempt AS varchar(2)) + ' : ' + CAST(@remaining AS varchar(10)) + ' table(s) en attente';
END;

PRINT '';
IF NOT EXISTS (
    SELECT 1 FROM sys.tables t
    INNER JOIN sys.schemas s ON t.schema_id = s.schema_id
    WHERE s.name = @source_schema
)
    PRINT 'Terminé — toutes les tables sont dans dbo.';
ELSE
    PRINT 'ATTENTION : des tables restent dans ' + @source_schema
        + '. Utilisez : python scripts/move_tables_to_dbo.py';

IF EXISTS (SELECT 1 FROM dbo.alembic_version)
    PRINT 'alembic_version : dbo OK';
