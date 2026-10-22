# Migration HFSQL → SIRV2 (SQL Server)

Scripts ETL pour l'import des données legacy HFSQL (WebDev) vers SQL Server SIRV2 (schéma `dbo`).

## Prérequis

- Driver **ODBC HFSQL 64 bits** (PC SOFT) sur le poste ETL réseau SENELEC
- Base SIRV2 migrée : `alembic upgrade head` + `seed_rbac`
- Copier `.env.migration.example` → `.env.migration` (gitignored)
- Profil cible : `SIR_PROFILE=senelec` (`.env.senelec` → srv-bddomtech/SIRV2)

## Configuration

```ini
# .env.migration
HFSQL_SERVER=srv-hfsql
HFSQL_PORT=4900
HFSQL_USER=admin
HFSQL_PASSWORD=***
HFSQL_DATABASE=SIR_ALHDL
SIR_PROFILE=senelec
MIGRATION_CUTOFF_YEARS=3
MIGRATION_DRY_RUN=true
```

Chaîne ODBC Client/Serveur :

```
DRIVER={HFSQL};Server Name=srv-hfsql;Server Port=4900;Database=<db>;UID=admin;PWD=***;IntegrityCheck=1
```

### PosteInterruption (SAIFI/SAIDI)

Les clients touchés par poste ne sont pas dans HFSQL exportable (volume > 16M lignes).
Source opérationnelle : **`srv-bddomtech` / `IndicateursTransportDistribution` / `dbo.PosteInterruption`**.

Cible SIRV2 `poste_interruptions` : `interruption_id`, `poste_id`, `nombre_clients_touches`,
plus dénormalisation `feeder_id`, `service_id`, `poste_source_id` (depuis l’interruption / poste / feeder).

```ini
# .env.migration (optionnel)
ITD_DATABASE=IndicateursTransportDistribution
```

```powershell
cd sir-backend
$env:SIR_PROFILE="senelec"
python ..\scripts\migration\import_poste_interruptions_itd.py --dry-run
python ..\scripts\migration\import_poste_interruptions_itd.py --execute --truncate
python ..\scripts\migration\backfill_poste_interruptions_context.py --execute
python ..\scripts\migration\recalculate_saifi_saidi.py --execute
```

> **Note** : utiliser **`pypyodbc`** (recommandé) — `pyodbc` peut crasher avec le driver HFSQL PC SOFT.

## Pipeline

| Étape | Commande |
|-------|----------|
| Test connexion | `python scripts/migration/test_prereq.py` |
| Audit source P0 | `python scripts/migration/audit_hfsql.py` |
| Extraction JSONL | `python scripts/migration/extract_hfsql.py` |
| ETL simulation | `python scripts/migration/etl_hfsql.py --dry-run --wave geo` |
| ETL import | `python scripts/migration/etl_hfsql.py --execute --wave all` |
| **Sync interruptions** | `python scripts/migration/sync_interruptions.py --execute` |
| **Import poste_interruptions (ITD)** | `python scripts/migration/import_poste_interruptions_itd.py --execute --truncate` |
| **Import sous-feeders** | `python scripts/migration/import_sous_feeders.py --execute` ou `bootstrap_sous_feeders.py --execute` |
| **Recalcul SAIFI/SAIDI** | `python scripts/migration/recalculate_saifi_saidi.py --execute` |
| Validation | `python scripts/migration/validate_migration.py` |

## Vagues ETL

| Vague | Contenu |
|-------|---------|
| `geo` | regions → delegations → agences → services |
| `referentiel` | causes, sieges, signalisations, natures, types_end |
| `reseau` | postes_sources, feeders, postes, troncons… |
| `utilisateurs` | utilisateurs + user_roles (bcrypt, reset obligatoire) |
| `interruptions` | interruptions unifiées + distribution/transport + poste_interruptions |
| `indicateurs` | energie_nd, saifi_saidi, nombre_client_mois |
| `napt` | napt, consignations, destinataires |

## Fichiers

| Chemin | Rôle |
|--------|------|
| `mapping.yaml` | Spécification mapping 107 tables → 37 tables dbo |
| `exports/*.jsonl` | Extraction HFSQL |
| `id_maps/*.json` | Correspondance legacy_id → sir_v2_id |
| `reports/` | Rapports audit et validation |
| `logs/etl_*.jsonl` | Lignes rejetées ETL |
| `runbook_cutover.md` | Procédure bascule et rollback |

## Rollback

Conserver exports HFSQL, id_maps et snapshots DB 3 mois post-migration. Voir `runbook_cutover.md`.
