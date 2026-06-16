# Migration HFSQL → SIR (Sprint 10)

Scripts ETL pour l'import des données legacy HFSQL vers PostgreSQL/SQL Server SIR.

## Prérequis

- Accès lecture HFSQL (ODBC ou export CSV)
- Base SIR migrée (`alembic upgrade head`)
- Variables d'environnement dans `.env.migration`

## Étapes

1. **Audit source** — `python scripts/migration/audit_hfsql.py`
2. **ETL** — `python scripts/migration/etl_hfsql.py --dry-run`
3. **Import** — `python scripts/migration/etl_hfsql.py --execute`
4. **Validation** — `python scripts/migration/validate_migration.py`

## Périmètre ETL

| Domaine | Tables cibles |
|---------|---------------|
| Référentiels | causes, natures, sieges, signalisations |
| Réseau | feeders, postes, postes_sources |
| Utilisateurs | utilisateurs, user_roles |
| Interruptions | interruptions, interruptions_distribution |
| Indicateurs | energie_nd, saifi_saidi |

## Rollback

Conserver les exports HFSQL et snapshots DB 3 mois post-migration.
