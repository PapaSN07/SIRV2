# CLAUDE.md — SIRV2 · SIR (Système d'Information Réseau) · SENELEC

> Fichier lu automatiquement par Claude Code à chaque session.
> Référence complète : [docs/CLAUDE_COWORK.md](docs/CLAUDE_COWORK.md) | Backlog : [docs/BACKLOG.md](docs/BACKLOG.md) | Sprint en cours : [docs/TODO.md](docs/TODO.md)

---

## Contexte projet

Migration de **SIR** (Système d'Information Réseau SENELEC) : WebDev + HFSQL → **FastAPI + SQL Server + Redis + Angular**.

Domaines : interruptions réseau électrique (MT/BT distribution + HTB transport), indicateurs SAIFI/SAIDI/END, rapports CRSE, NAPT, notifications SMS/Email.

Référence indicateurs (formules, endpoints, RBAC) : [docs/indicateurs_sirv2.md](docs/indicateurs_sirv2.md).

Répertoires cibles : `sir-backend/` (FastAPI) et `sir-frontend/` (Angular 17+).

---

## Règles absolues — ne jamais enfreindre

### Sécurité
- `password_hash` bcrypt uniquement — jamais de mot de passe en clair, jamais dans les logs ni les réponses API
- Auth JWT sur tous les endpoints sauf `POST /api/v1/auth/login` et `POST /api/v1/auth/refresh`
- Vérification RBAC en **double** : décorateur `@require_permission` sur le router **ET** clause `WHERE service_id = :uid` dans la requête SQL

### Schéma base de données
- Alembic pour tout changement de schéma — zéro DDL manuel
- Jamais `SELECT *` — colonnes explicites toujours
- `DATETIME2` pour toutes les dates/heures — jamais deux colonnes séparées `date` + `heure`
- FK obligatoires — jamais de nom en VARCHAR à la place d'un ID

### Architecture
- Logique métier dans `services/` uniquement — jamais dans les routers
- Accès DB dans `repositories/` uniquement — les services n'appellent pas SQLAlchemy directement
- Calculs lourds (SAIFI/SAIDI 12 mois, génération rapports) via **Celery** — jamais synchrone dans un endpoint
- Schéma de réponse Pydantic explicite sur chaque endpoint — jamais `dict` générique

---

## RBAC — Périmètres

| Rôle | Peut créer/modifier | Périmètre de lecture | Peut valider |
|---|---|---|---|
| `BCC` | interruptions distribution | son `service_id` uniquement | non |
| `BRC` | — | sa `region_id` | non |
| `DISPATCHER` | interruptions transport | transport uniquement | non |
| `ADMIN_SCR` | distribution national | distribution uniquement (**pas transport**) | oui (distribution) |
| `ADMIN_DISPATCHING` | transport national | transport uniquement | oui (transport) |
| `ADMIN_SAQS` | — | tout, **lecture seule** | oui (tous) |
| `SUPERVISEUR` | — | son service | oui (son service) |

---

## Ne pas implémenter sans validation SENELEC

| Sujet | Raison du blocage |
|---|---|
| Formules de pondération END (CRSE) | Règles exactes non confirmées par l'équipe SENELEC |
| Exclusions/pondérations SAIFI/SAIDI | Idem |
| Format des rapports réglementaires | À fournir par l'équipe SAQS |
| Scripts ETL sur données réelles | Tester sur dump HFSQL avant toute exécution |

---

## Stack technique

### Backend (`sir-backend/`)
- Python 3.12 · FastAPI 0.115+ · SQLAlchemy 2.0 async · Pydantic v2 · Alembic 1.13+
- Auth : JWT HS256 (`python-jose`), bcrypt (`passlib`), blacklist JTI dans Redis
- Driver SQL Server : `aiomssql` (async)
- Workers : Celery 5.x, broker `redis://localhost:6379/1`, results `redis://localhost:6379/2`
- Exports : `openpyxl` (Excel), `reportlab` (PDF)

### Frontend (`sir-frontend/`)
- Angular 17+ · TypeScript 5.x · Angular Material 17+ · NgRx · RxJS 7
- Lazy loading obligatoire sur tous les modules `features/`
- `RoleGuard` sur toutes les routes sensibles

### Infrastructure
- SQL Server 2019+ · Redis 7+ · Docker Compose

---

## Conventions de code

### Python
- `snake_case` partout : variables, fonctions, fichiers, colonnes DB
- Type hints obligatoires sur toutes les fonctions
- `async/await` partout — zéro opération synchrone bloquante
- Réponse enveloppée : `{"status": "success"|"error", "data": ..., "error": null}`

### Endpoints REST
- URLs noms pluriels, versionnées : `GET /api/v1/interruptions/distribution`
- Routes statiques déclarées **avant** les routes dynamiques (`/by-date/` avant `/{id}`)
- Listes paginées : `?page=1&size=20` → réponse avec `total`, `page`, `size`, `items`

### TypeScript
- `camelCase` variables/fonctions · `PascalCase` classes/interfaces
- Interfaces pour tous les modèles — zéro `any`
- Services Angular pour tous les appels HTTP — jamais `HttpClient` dans les composants
- Lire le schéma Pydantic backend avant de coder un service frontend

---

## Redis — Clés et TTL

| Clé | Usage | TTL |
|---|---|---|
| `indicateurs:{type}:{region_id}:{annee}:{mois}` | Cache END/SAIFI/SAIDI | 1h |
| `jwt:blacklist:{jti}` | Tokens révoqués | durée restante du token |
| `referentiel:{ressource}` | Causes, sièges, signalisations | 24h |
| `ratelimit:{user_id}` | Rate limiting | 1 min glissante |

Pattern : lire Redis → miss → calculer DB → écrire Redis → retourner.

---

## Authentification JWT

- Access token : TTL 30 min · Refresh token : TTL 7 jours (cookie HttpOnly)
- Logout : JTI ajouté à la blacklist Redis avec TTL = durée restante
- Première connexion : `premiere_connexion = True` → forcer changement de mot de passe

---

## Décisions structurantes

| Date | Décision | Statut |
|---|---|---|
| Juin 2026 | Stack FastAPI + SQL Server 2019+ + Redis 7 + Angular 17+ | Validé |
| Juin 2026 | Table `interruptions` unifiée, discriminant `type_direction` | Validé |
| Juin 2026 | Référentiels unifiés — une seule table `causes` avec `type_reseau` | Validé |
| Juin 2026 | Scope RBAC dans `user_roles.scope_service_id` | Validé |
| Juin 2026 | Mode de migration Big Bang vs Progressif | **En attente** |

---

## Gestion des erreurs rencontrées

Quand Claude rencontre une erreur en travaillant sur ce projet :

1. **Corriger** l'erreur immédiatement dans le code
2. **Documenter** dans la section ci-dessous : ce qui s'est passé, pourquoi, et la règle à retenir
3. **Proposer** si nécessaire une mise à jour du `CLAUDE.md` global (`~/.claude/CLAUDE.md`) si l'erreur est générique et peut survenir sur d'autres projets

### Erreurs documentées

<!-- Format : ### [Date] — [Titre court]
**Contexte** : où / dans quel fichier
**Erreur** : ce qui s'est passé
**Correction** : ce qui a été changé
**Règle** : la règle à appliquer à l'avenir
-->

Aucune erreur documentée pour l'instant.

---

*Dernière mise à jour : Juin 2026*
