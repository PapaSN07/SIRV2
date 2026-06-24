# Runbook bascule HFSQL → SQL Server SIRV2

## Prérequis

- [ ] Driver ODBC HFSQL 64 bits installé sur le poste ETL
- [ ] DSN ou `.env.migration` validé (`python scripts/migration/test_prereq.py`)
- [ ] `alembic upgrade head` sur SIRV2 (schéma `dbo`)
- [ ] `seed_rbac` exécuté (rôles/permissions — **pas** `run_seed_dev` complet)
- [ ] Snapshot backup base `SIRV2` avant import

## J-7 — Préparation

1. Audit source : `python scripts/migration/audit_hfsql.py`
2. Valider rapport `scripts/migration/reports/audit_YYYYMMDD.json` avec métier SAQS/SCR
3. Extraction complète : `python scripts/migration/extract_hfsql.py`
4. ETL dry-run par vague :
   ```powershell
   python scripts/migration/etl_hfsql.py --dry-run --wave geo
   python scripts/migration/etl_hfsql.py --dry-run --wave referentiel
   python scripts/migration/etl_hfsql.py --dry-run --wave reseau
   python scripts/migration/etl_hfsql.py --dry-run --wave utilisateurs
   python scripts/migration/etl_hfsql.py --dry-run --wave interruptions
   ```

## J-1 — Import pré-production

1. Restaurer snapshot SIRV2 vierge (référentiels RBAC uniquement)
2. Import réel :
   ```powershell
   $env:MIGRATION_DRY_RUN="false"
   python scripts/migration/etl_hfsql.py --execute --wave all
   ```
3. Validation : `python scripts/migration/validate_migration.py`
4. Corriger rejets dans `scripts/migration/logs/etl_*.jsonl`

## Jour J — Cutover (fenêtre maintenance)

| Heure | Action |
|-------|--------|
| T-60 | Communication utilisateurs — reset mot de passe obligatoire |
| T-30 | Geler saisies WebDev / HFSQL (lecture seule) |
| T-15 | Snapshot final SIRV2 pre-delta |
| T-10 | Export delta : `python scripts/migration/extract_hfsql.py` |
| T-5 | ETL delta : `python scripts/migration/etl_hfsql.py --execute --wave interruptions` |
| T-0 | Validation finale : `python scripts/migration/validate_migration.py` → **GO** |
| T+0 | Basculer API/frontend : `SIR_PROFILE=senelec` |
| T+30 | Smoke tests : login, liste interruptions, création BCC |

## Rollback

1. Repointage API vers HFSQL/WebDev legacy
2. Restaurer snapshot `SIRV2` pre-migration
3. Conserver exports JSONL + `scripts/migration/id_maps/` pour rejeu
4. Analyser écarts dans `validation_YYYYMMDD.json`

## Post-bascule

- HFSQL en **lecture seule 3 mois** (BACKLOG 10.6)
- Communication reset mots de passe (`premiere_connexion=True` pour tous les migrés)
- Ne jamais conserver ni logger les mots de passe source HFSQL

## Contacts

| Rôle | Action |
|------|--------|
| DBA | Snapshots, droits LectSIP, performance batch |
| SAQS | Validation counts END/SAIFI/SAIDI |
| SCR | Validation référentiels réseau |
| Intégration | Smoke tests post-bascule |
