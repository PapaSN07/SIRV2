# TODO — SIR (Sprint 1 ✅ · … · Sprint 6 ✅ · Sprint 8 ✅ backend)

> Légende : `[ ]` à faire · `[~]` en cours · `[x]` terminé · `[!]` bloqué
>
> **Sprint courant :** Sprint 8 ✅ backend · E2E / validation SMTP staging restants

---

## Avancement global

| Phase | Titre | Statut |
| --- | --- | --- |
| **Sprint 1** | | |
| 1.1 | Setup infrastructure | ✅ Terminé (CI pipeline manquant, non bloquant) |
| 1.2 | Schéma DB + Alembic | ✅ Terminé |
| 1.3 | Authentification JWT | ✅ Terminé |
| 1.4 | Système RBAC | ✅ Terminé |
| **Sprint 2** | | |
| 1.5 | Admin utilisateurs (report Sprint 1) | ✅ Terminé |
| 2.1 | Référentiels partagés | ✅ Terminé |
| 2.2 | Organisation géographique | ✅ Terminé |
| 2.3 | Réseau Distribution | ✅ Terminé |
| 2.4 | Réseau Transport | ✅ Terminé |
| **Sprint 3** | | |
| 3.1 | Création interruption distribution | ✅ Terminé |
| 3.2 | Liste interruptions distribution | ✅ Terminé |
| 3.3 | Détail interruption | ✅ Terminé |
| 3.4 | Modification interruption | ✅ Terminé |
| 3.5 | Clôture interruption | ✅ Terminé |
| 3.6 | Validation interruption | ✅ Terminé |
| 3.7 | Association postes impactés | ✅ Terminé |
| 3.8 | Calcul END (service + worker) | ✅ Terminé |
| **Sprint 4** | | |
| 4.1 | Création interruption transport | ✅ Terminé |
| 4.2 | Liste + détail interruptions transport | ✅ Terminé |
| 4.3 | Modification / clôture transport | ✅ Terminé |
| 4.4 | Validation transport | ✅ Terminé |
| 4.5 | Interruptions OMVG | ✅ Terminé |
| **Sprint 5** | | |
| 5.1 | Calcul SAIFI/SAIDI (service + worker) | ✅ Terminé |
| 5.2 | Cache Redis indicateurs | ✅ Terminé |
| 5.3 | Tableau de bord indicateurs | ✅ Terminé |
| 5.4 | Endpoints indicateurs détaillés | ✅ Terminé |
| 5.5 | Historique 12 mois | ✅ Terminé |
| 5.6 | Classement feeders par END | ✅ Terminé |
| **Sprint 6** | | |
| 6.6 | Génération asynchrone (Celery + suivi + notification) | ✅ Terminé |
| 6.1 | Rapport journalier | ✅ Terminé |
| 6.2 | Rapport mensuel distribution | ✅ Terminé |
| 6.3 | Rapport mensuel transport | ✅ Terminé |
| 6.5 | Classement feeders dans rapports | ✅ Terminé |
| 6.4 | Rapport annuel | ✅ Terminé |
| **Sprint 8** | | |
| 8.3 | Gestion destinataires | ✅ Terminé |
| 8.2 | Envoi Email | ✅ Terminé |
| 8.1 | Envoi SMS | ✅ Terminé |
| 8.4 | Notifications temps réel (SSE) | ✅ Terminé |

**Ordre Sprint 3 :** 3.1 → 3.2 → 3.3 → 3.7 → 3.4 → 3.5 → 3.8 → 3.6

**Ordre Sprint 4 :** 4.1 → 4.2 → 4.3 → 4.4 → 4.5

**Ordre Sprint 5 :** 5.1 → 5.2 → 5.4 → 5.3 → 5.5 → 5.6

**Ordre Sprint 6 :** 6.6 → 6.1 → 6.2 → 6.5 → 6.3 → 6.4

**Ordre Sprint 8 :** 8.3 → 8.2 → 8.1 → 8.4

---

# Sprint 1 — Fondations ✅

> Validation QA : **67 tests passés** · migration `771d41b833c8_initial_schema.py` · upgrade/downgrade OK
>
> Notes : `seed_rbac(db)` prêt mais pas automatisé au démarrage · frontend Angular non initialisé · routers stub vides (`referentiel`, `reseau`, `admin`)

---

## Phase 1.1 — Setup infrastructure

- [x] Docker Compose : FastAPI + SQL Server 2019 + Redis 7 + worker Celery
- [x] Stack backend seule (`db`, `redis`, `api`, `worker`) — pas de build frontend sans `package.json`
- [x] `requirements.txt` avec versions épinglées (`aioodbc`, `pyodbc`, `bcrypt==4.0.1`, …)
- [x] `.env` + `.env.example` — parsing `CORS_ORIGINS` corrigé (`config.py`)
- [x] `Makefile` : `make dev`, `make test`, `make migrate`, `make upgrade`, `make downgrade`
- [x] ODBC Driver 18 + healthcheck SQL Server (`sqlcmd` tools18)
- [ ] Pipeline CI (lint + tests automatiques) — non bloquant

---

## Phase 1.2 — Schéma DB + migration Alembic

### Modèles SQLAlchemy (`sir-backend/app/models/`)

- [x] `utilisateurs.py` — `Utilisateur`, `Role`, `Permission`, `RolePermission`, `UserRole`
- [x] `geo.py` — `Region`, `Delegation`, `Agence`, `Service`
- [x] `reseau.py` — `Feeder`, `PosteSource`, `Poste`, `Troncon`, `SousFeeder`, `EquipementTransport`, `SourceTransport`, `PosteLigne`
- [x] `interruptions.py` — `Interruption`, `InterruptionDistribution`, `InterruptionTransport`, `PosteInterruption`
- [x] `referentiel.py` — `Cause`, `Siege`, `Signalisation`, `Nature`, `TypeEnd`
- [x] `indicateurs.py` — `EnergieNd`, `SaifiSaidi`, `NombreClientMois`
- [x] `napt.py` — `Napt`, `Consignation`
- [x] `notifications.py` — `SmsEnvoye`, `EmailEnvoye`, `Destinataire`
- [x] `audit.py` — `AuditLog`
- [x] `defaults.py` — `MSSQL_NOW` (DATETIME2)
- [x] `app/models/__init__.py` — import de tous les modèles pour Alembic

### Migration

- [x] Migration `771d41b833c8_initial_schema.py` générée et appliquée
- [x] `make upgrade` — OK
- [x] `make downgrade` — rollback propre

---

## Phase 1.3 — Authentification JWT

### Fichiers

- [x] `app/schemas/auth.py` — `LoginRequest`, `TokenResponse`, `RefreshRequest`, `MeResponse`
- [x] `app/repositories/utilisateur_repository.py` — `get_by_login()`, `get_by_id()`
- [x] `app/services/auth_service.py` — `login()`, `refresh()`, `logout()`, `get_current_user()`
- [x] `app/api/v1/auth/router.py` — 4 endpoints

### Endpoints

- [x] `POST /api/v1/auth/login` → access token (body) + refresh token (cookie HttpOnly)
- [x] `POST /api/v1/auth/refresh` → nouveau access token
- [x] `DELETE /api/v1/auth/logout` → blacklist JTI dans Redis
- [x] `GET /api/v1/auth/me` → profil utilisateur connecté

### Comportements critiques

- [x] `premiere_connexion = True` → réponse 403 avec code `FORCE_PASSWORD_CHANGE`
- [x] JTI blacklisté dans Redis au logout (TTL = durée restante du token)
- [x] Jamais de mot de passe dans les logs ni dans les réponses

### Tests (`tests/integration/test_auth_endpoints.py`)

- [x] Login OK → 200 + tokens
- [x] Login mauvais mot de passe → 401
- [x] Login utilisateur inactif → 403
- [x] Access token expiré → 401
- [x] Logout puis réutilisation du token → 401
- [x] Refresh avec cookie valide → 200

---

## Phase 1.4 — Système RBAC

### Fichiers

- [x] `app/core/deps.py` — `get_current_user()`, `require_role(*roles)`, `require_permission(ressource, action)`
- [x] `app/repositories/rbac_repository.py` — `get_user_permissions()`, `get_user_scope()`
- [x] `app/models/seed/seed_rbac.py` — seeding des 7 rôles et permissions initiales

### Rôles seedés (script)

- [x] `BCC` — interruptions:distribution (create, read, update)
- [x] `BRC` — interruptions:distribution (read)
- [x] `DISPATCHER` — interruptions:transport (create, read, update)
- [x] `ADMIN_SCR` — distribution (create, read, update, validate), admin:utilisateurs
- [x] `ADMIN_DISPATCHING` — transport (create, read, update, validate), admin:utilisateurs
- [x] `ADMIN_SAQS` — tout (read only)
- [x] `SUPERVISEUR` — interruptions (read, validate scope)

### Tests (`tests/unit/test_rbac.py` + intégration)

- [x] BCC avec `service_id` différent → 403
- [x] BRC lecture sur sa région → 200
- [x] Admin SCR sur endpoint transport → 403
- [x] Admin SAQS lecture → 200, création → 403
- [x] Dispatcher sur endpoint distribution → 403
- [x] Superviseur validation interruption de son service → 200

---

## Tâches transverses Sprint 1

- [x] `app/utils/pagination.py` — helper `paginate(query, page, size)`
- [x] `app/utils/audit.py` — helper `log_audit(db, table, action, user_id, data)`
- [x] `app/schemas/common.py` — `PaginatedResponse[T]`, `ApiResponse[T]`
- [x] Routers stub enregistrés : `auth`, `admin`, `referentiel`, `reseau`, `interruptions`, `indicateurs`, `napt`, `notifications`, `rapports`

---

## Definition of done — Sprint 1 ✅

- [x] Phases 1.1–1.4 cochées (CI pipeline excepté)
- [x] `make test` vert — 67 tests passés
- [x] Migration Alembic upgrade + downgrade OK
- [x] API healthy sur `:8000` (Swagger `/api/docs`)
- [x] `docs/BACKLOG.md` §1.1–1.4 synchronisé

---

# Sprint 2 — Référentiels, Géo & Réseau ✅

---
## Phase 1.5 — Admin utilisateurs (report BACKLOG §1.5)

> Nécessaire avant la saisie métier · modèles déjà en place (Sprint 1)

### Fichiers à créer

- [x] `app/schemas/admin.py` — `UtilisateurCreate`, `UtilisateurUpdate`, `UtilisateurResponse`, `ResetPasswordRequest`
- [x] `app/repositories/admin_utilisateur_repository.py` — CRUD + filtres direction (SCR vs Dispatching)
- [x] `app/services/admin_utilisateur_service.py` — logique métier + RBAC + attribution rôles/scope
- [x] Compléter `app/api/v1/admin/router.py`

### Endpoints

- [x] `GET /api/v1/admin/utilisateurs` — liste paginée, filtrée par direction (Admin SCR vs Admin Dispatching)
- [x] `POST /api/v1/admin/utilisateurs` — création + hash bcrypt + `premiere_connexion=True`
- [x] `PUT /api/v1/admin/utilisateurs/{id}` — mise à jour profil
- [x] `PATCH /api/v1/admin/utilisateurs/{id}/activer` — activation compte
- [x] `PATCH /api/v1/admin/utilisateurs/{id}/desactiver` — désactivation compte
- [x] `POST /api/v1/admin/utilisateurs/{id}/reset-password` — reset mot de passe

### Comportements critiques

- [x] RBAC : `@require_permission("admin_utilisateurs", …)` sur tous les endpoints
- [x] Admin SCR → périmètre distribution uniquement ; Admin Dispatching → transport uniquement
- [x] Attribution rôles + `scope_service_id` / scope région via `user_roles`
- [x] Exécuter `seed_rbac(db)` en base — via `make seed-dev`

### Tests (`tests/integration/test_admin_utilisateurs.py`)

- [x] Admin SCR liste utilisateurs distribution → 200
- [x] Admin Dispatching accès admin SCR-only → 403
- [x] BCC accès endpoint admin → 403
- [x] Création utilisateur → 201 + `premiere_connexion=True`
- [x] Reset password → login avec nouveau mot de passe OK

---

## Phase 2.1 — Référentiels partagés (BACKLOG §2.1)

> Modèles existants : `app/models/referentiel.py` · Router stub : `app/api/v1/referentiel/router.py`

### Fichiers à créer

- [x] `app/schemas/referentiel.py` — Create/Update/Response pour chaque ressource
- [x] `app/repositories/referentiel_repository.py` — CRUD générique par table
- [x] `app/services/referentiel_service.py` — logique + cache Redis + invalidation
- [x] Compléter `app/api/v1/referentiel/router.py`

### Ressources (5 tables)

- [x] `causes` — CRUD, filtre `type_reseau` (distribution | transport | commun)
- [x] `sieges` — CRUD + `type_reseau`
- [x] `signalisations` — CRUD + `type_reseau`
- [x] `natures` — CRUD
- [x] `types_end` — CRUD

### Endpoints

- [x] `GET /api/v1/referentiel/{ressource}` — liste (tous rôles authentifiés)
- [x] `GET /api/v1/referentiel/{ressource}/{id}` — détail
- [x] `POST /api/v1/referentiel/{ressource}` — BCC / Admin SAQS → 403 ; Admin SCR / Dispatching → 201
- [x] `PUT /api/v1/referentiel/{ressource}/{id}` — Admin uniquement
- [x] `DELETE /api/v1/referentiel/{ressource}/{id}` — Admin uniquement (soft delete `is_active=False`)

### Cache Redis

- [x] Clé `referentiel:{ressource}` — TTL 24h (version bump)
- [x] Invalidation cache sur POST/PUT/DELETE
- [x] Pattern : read cache → miss → DB → set cache

### Tests (`tests/integration/test_referentiel.py`)

- [x] GET causes → 200 + liste paginée
- [x] POST cause en tant que BCC → 403
- [x] POST cause en tant qu'Admin SCR → 201
- [x] Modification → cache invalidé (2e GET reflète la modification)
- [x] Filtre `type_reseau=distribution` sur causes → résultats cohérents

---

## Phase 2.2 — Organisation géographique (BACKLOG §2.2)

> Modèles existants : `app/models/geo.py` · **Nouveau module** : `app/api/v1/geo/`

### Fichiers à créer

- [x] `app/schemas/geo.py` — `RegionResponse`, `DelegationResponse`, `AgenceResponse`, `ServiceResponse`
- [x] `app/repositories/geo_repository.py` — lecture hiérarchique
- [x] `app/services/geo_service.py`
- [x] `app/api/v1/geo/router.py` — 4 endpoints lecture seule
- [x] Enregistrer le router dans `app/api/v1/router.py` (`prefix="/geo"`)

### Endpoints (lecture seule — tous rôles authentifiés)

- [x] `GET /api/v1/geo/regions`
- [x] `GET /api/v1/geo/delegations?region_id=`
- [x] `GET /api/v1/geo/agences?delegation_id=`
- [x] `GET /api/v1/geo/services?agence_id=`

### Données de seed

- [x] `app/models/seed/seed_geo.py` — régions / délégations / agences / services SENELEC (jeu minimal dev)
- [x] Commande `make seed-geo` / `python -m scripts.run_seed_geo`

### Tests (`tests/integration/test_geo.py`)

- [x] GET regions → 200 + liste non vide (après seed)
- [x] GET delegations avec `region_id` valide → 200
- [x] GET sans token → 403 (HTTPBearer)
- [x] Chaîne regions → delegations → agences → services cohérente

---

## Phase 2.3 — Réseau Distribution (BACKLOG §2.3)

> Modèles existants : `app/models/reseau.py` (partie distribution) · Router stub : `app/api/v1/reseau/router.py`

### Fichiers à créer

- [x] `app/schemas/reseau_distribution.py` — Feeder, PosteSource, Poste, Troncon, SousFeeder
- [x] `app/repositories/reseau_distribution_repository.py`
- [x] `app/services/reseau_distribution_service.py` — RBAC BCC/BRC lecture, Admin SCR écriture
- [x] Routes dans `app/api/v1/reseau/router.py`

### Entités CRUD

- [x] `postes_sources` — CRUD, filtre `region_id`
- [x] `feeders` — CRUD, filtre `poste_source_id`, `service_id`
- [x] `postes` — CRUD, association feeder
- [x] `troncons` — CRUD
- [x] `sous_feeders` — CRUD, association feeder

### Endpoints

- [x] `GET /api/v1/reseau/feeders` — liste paginée + filtres
- [x] `POST /api/v1/reseau/feeders` — Admin SCR uniquement
- [x] `GET /api/v1/reseau/feeders/{id}`
- [x] `PUT /api/v1/reseau/feeders/{id}`
- [x] Idem pour `postes-sources`, `postes`, `troncons`, `sous-feeders`

### RBAC

- [x] Lecture : BCC, BRC, Admin SCR, Admin SAQS (scope service/région appliqué)
- [x] Écriture : Admin SCR uniquement
- [x] BCC tentative POST → 403

### Tests (`tests/integration/test_reseau_distribution.py`)

- [x] BCC GET feeders de son service → 200
- [x] BCC GET feeders autre service → liste vide
- [x] Admin SCR POST feeder → 201
- [x] Dispatcher POST feeder → 403

---

## Phase 2.4 — Réseau Transport (BACKLOG §2.4)

> Modèles existants : `EquipementTransport`, `SourceTransport`, `PosteLigne`

### Fichiers à créer

- [x] `app/schemas/reseau_transport.py`
- [x] `app/repositories/reseau_transport_repository.py`
- [x] `app/services/reseau_transport_service.py`
- [x] Routes transport dans `app/api/v1/reseau/transport/router.py`

### Entités CRUD

- [x] `equipements_transport` — lignes HTB, transformateurs, etc.
- [x] `sources_transport`
- [x] `postes_lignes`

### Endpoints

- [x] CRUD complet pour les 3 entités sous `/api/v1/reseau/transport/…`

### RBAC

- [x] Lecture : DISPATCHER, Admin Dispatching, Admin SAQS
- [x] Écriture : Admin Dispatching uniquement
- [x] Admin SCR accès transport → 403

### Tests (`tests/integration/test_reseau_transport.py`)

- [x] DISPATCHER GET equipements → 200
- [x] Admin Dispatching POST equipement → 201
- [x] Admin SCR GET transport → 403
- [x] BCC GET transport → 403

---

## Tâches transverses Sprint 2

### Backend

- [x] Réutiliser `paginate()` et `ApiResponse[T]` sur tous les endpoints liste
- [x] `log_audit()` sur toutes les mutations (POST/PUT/DELETE/PATCH)
- [x] Seeds dev : `make seed-dev` (RBAC + geo + réseau) · `make seed-rbac` · `make seed-geo` · `make seed-reseau`
- [x] Exécuter `seed_rbac(db)` en base — via `make seed-dev`

### Frontend (sir-frontend)

- [x] Initialiser projet Angular 17 (`package.json`, structure `features/`)
- [x] Module **auth** : login, intercepteur JWT, `AuthService`, `authGuard` / `roleGuard`
- [x] Module **referentiel** : listes causes/sièges/signalisations (lecture)
- [x] Module **geo** : cascades region → délégation → agence → service
- [x] Alignement interfaces TS ↔ schémas Pydantic (`sir-integration`)

### Integration & QA

- [x] Rapport `docs/integration/INTEGRATION_REPORT_referentiel.md`
- [x] Rapport `docs/integration/INTEGRATION_REPORT_geo_reseau.md`
- [x] Couverture tests : chaque phase → tests intégration verts

---

## Definition of done — Sprint 2

- [x] Toutes les phases 1.5, 2.1, 2.2, 2.3, 2.4 cochées
- [x] `make test` vert (suite complète backend)
- [x] Seeds dev chargés (geo + réseau minimal) — `make seed-dev`
- [x] Module auth frontend fonctionnel (login → `/auth/me`)
- [x] Modules frontend referentiel + geo (lecture)
- [x] BACKLOG §1.5 et §2.1–2.4 mis à jour dans `docs/BACKLOG.md`

---

# Sprint 3 — Interruptions Distribution

> **BACKLOG Phase 3** — Cœur métier #1 · Priorité P0
>
> Prérequis : Sprint 1 + Sprint 2 ✅ · Modèles existants : `app/models/interruptions.py` · Router stub : `app/api/v1/interruptions/distribution/router.py`

---

## Phase 3.1 — Création interruption distribution (BACKLOG §3.1)

### Fichiers à créer

- [x] `app/schemas/interruption_distribution.py` — `InterruptionDistributionCreate`, `InterruptionDistributionUpdate`, `InterruptionDistributionResponse`, `InterruptionDistributionFilters`
- [x] `app/repositories/interruption_distribution_repository.py` — insert `interruptions` + `interruptions_distribution`, génération `numero_interruption`
- [x] `app/services/interruption_distribution_service.py` — validation métier + RBAC scope `service_id`
- [x] Compléter `app/api/v1/interruptions/distribution/router.py`

### Endpoint

- [x] `POST /api/v1/interruptions/distribution` — création interruption distribution

### Comportements critiques

- [x] RBAC : BCC → `service_id` de l'utilisateur uniquement (via scope `user_roles.scope_service_id`)
- [x] BRC / Admin SCR / Admin SAQS / Superviseur — règles lecture/écriture selon permissions `interruptions:distribution`
- [x] Auto-génération `numero_interruption` (max+1 par année civile)
- [x] Champs obligatoires : `date_apparition`, `feeder_id`, `cause_id`, `nature_id`, `siege_id`, `signalisation_id`
- [x] `type_direction = 'distribution'` · statut initial `en_cours`
- [x] Insertion ligne `interruptions_distribution` (1-to-1)
- [x] `log_audit()` sur création
- [x] Dispatcher / Admin Dispatching → 403

### Tests (`tests/integration/test_interruption_distribution_create.py`)

- [x] BCC crée interruption sur son service → 201 + `statut=en_cours` + `numero_interruption` renseigné
- [x] BCC hors périmètre (feeder autre service) → 403
- [x] Champs manquants → 422
- [x] Dispatcher POST distribution → 403

---

## Phase 3.2 — Liste interruptions distribution (BACKLOG §3.2)

### Fichiers à compléter

- [x] `interruption_distribution_repository.py` — requêtes filtrées + scope BCC/BRC/Admin
- [x] `interruption_distribution_service.py` — agrégation filtres
- [x] Routes liste dans `distribution/router.py`

### Endpoint

- [x] `GET /api/v1/interruptions/distribution` — liste paginée

### Filtres query

- [x] `region_id`, `feeder_id`, `statut`, `date_debut`, `date_fin`
- [x] Pagination `page` / `page_size` · tri `date_apparition DESC`

### Scope automatique

- [x] BCC → son `service_id` uniquement
- [x] BRC → sa `region_id` (via scope ou dérivation agence)
- [x] Admin SCR / Admin SAQS → tout le périmètre distribution
- [x] Superviseur → scope service/région selon attribution

### Tests (`tests/integration/test_interruption_distribution_list.py`)

- [x] BCC liste → 200, uniquement interruptions de son service
- [x] Filtre `statut=en_cours` → résultats cohérents
- [x] Filtre `date_debut` / `date_fin` → plage respectée
- [x] Pagination : `total`, `page`, `page_size` cohérents

---

## Phase 3.3 — Détail interruption (BACKLOG §3.3)

### Endpoint

- [x] `GET /api/v1/interruptions/distribution/{id}` — détail complet

### Contenu réponse

- [x] Champs interruption + détail `interruptions_distribution`
- [x] Libellés jointure : feeder, cause, nature, siège, signalisation, service
- [x] Postes impactés (liste `poste_interruptions` + libellé poste)
- [x] END calculée si clôturée (`energie_nd` ou `end_mwh`)
- [x] Métadonnées audit : `created_by`, `created_at`, `updated_at`, `validated_by`

### RBAC

- [x] Même scope que liste — BCC hors périmètre → 403

### Tests (`tests/integration/test_interruption_distribution_detail.py`)

- [x] GET détail interruption existante → 200 + structure complète
- [x] BCC accès interruption autre service → 403
- [x] ID inexistant → 404

---

## Phase 3.7 — Association postes impactés (BACKLOG §3.7)

> Implémenter avant clôture (3.5) — validation métier « au moins 1 poste avant clôture »

### Fichiers à compléter

- [x] `interruption_distribution_repository.py` — CRUD `poste_interruptions`
- [x] Méthodes postes dans `interruption_distribution_service.py`

### Endpoints

- [x] `GET /api/v1/interruptions/distribution/{id}/postes` — liste postes impactés
- [x] `POST /api/v1/interruptions/distribution/{id}/postes` — ajout poste (+ `nombre_clients_touches` optionnel)
- [x] `DELETE /api/v1/interruptions/distribution/{id}/postes/{poste_id}` — retrait poste

### Comportements critiques

- [x] Uniquement si statut = `en_cours`
- [x] Poste doit appartenir au périmètre feeder/service de l'interruption
- [x] Contrainte unicité `(interruption_id, poste_id)`
- [x] `log_audit()` sur ajout/suppression

### Tests (`tests/integration/test_interruption_distribution_postes.py`)

- [x] POST poste sur interruption en_cours → 201
- [x] POST poste sur interruption clôturée → 403 ou 422
- [x] DELETE poste → 204
- [x] GET liste postes → 200 + count cohérent

---

## Phase 3.4 — Modification interruption (BACKLOG §3.4)

### Endpoint

- [x] `PUT /api/v1/interruptions/distribution/{id}` — mise à jour

### Comportements critiques

- [x] Uniquement si statut = `en_cours`
- [x] Seul le créateur (`created_by_id`) ou Admin SCR peut modifier
- [x] BCC peut modifier ses propres interruptions (scope service)
- [x] Champs modifiables : caractérisation, observations, puissance, localisation, flags FM/fugitif
- [x] `log_audit()` à chaque modification (table `audit_log`)

### Tests (`tests/integration/test_interruption_distribution_update.py`)

- [x] Créateur PUT → 200
- [x] Autre BCC PUT → 403
- [x] PUT sur interruption `cloture` → 403 ou 422
- [x] Audit log enregistré après modification

---

## Phase 3.5 — Clôture interruption (BACKLOG §3.5)

### Endpoint

- [x] `PATCH /api/v1/interruptions/distribution/{id}/cloturer` — clôture avec `date_remise`

### Comportements critiques

- [x] Saisie `date_remise` obligatoire · `date_remise > date_apparition`
- [x] Au moins 1 poste impacté (validation service — cf. 3.7)
- [x] Calcul `duree_minutes` = différence en minutes
- [x] Statut → `cloture`
- [x] Déclenchement tâche Celery `calcul_end` (async, cf. 3.8)
- [x] `log_audit()` sur clôture

### Tests (`tests/integration/test_interruption_distribution_cloture.py`)

- [x] Clôture sans postes → 422
- [x] Clôture `date_remise` invalide → 422
- [x] Clôture OK → 200 + `statut=cloture` + `duree_minutes` renseigné
- [x] Tâche Celery `calcul_end` enqueued (mock ou worker test)

---

## Phase 3.8 — Calcul END (service + worker) (BACKLOG §3.8)

> **⚠ Formules CRSE à valider avec équipe SENELEC** — implémenter placeholder documenté si non confirmé

### Fichiers à créer

- [x] `app/services/end_service.py` — `calcul_end(puissance_mw, duree_h) → Decimal`
- [x] `app/repositories/end_repository.py` — persistance `energie_nd`
- [x] `app/workers/tasks/indicateurs.py` — tâche Celery `calcul_end(interruption_id)`
- [x] Enregistrer module dans `app/workers/celery_app.py` (include déjà prévu)

### Logique métier

- [x] Exclusion interruptions force majeure (`is_force_majeure=True` → END = 0)
- [x] Application règles `types_end` / `regles_end` (placeholder `REGLES_END_PAR_NATURE` — table `regles_end` absente, CRSE à valider)
- [x] Persistance table `energie_nd` + miroir `interruptions_distribution.end_mwh`
- [x] Cache Redis clé `indicateurs:end:{region_id}:{periode}` — invalidation sur calcul

### Tests

- [x] `tests/unit/test_end_service.py` — `assert calcul_end(5.0, 2.0) == 10.0`
- [x] Force majeure → END = 0.0
- [x] Tâche Celery persiste `energie_nd` après clôture (test unitaire worker mock)

---

## Phase 3.6 — Validation interruption (BACKLOG §3.6)

### Endpoint

- [x] `PATCH /api/v1/interruptions/distribution/{id}/valider` — validation hiérarchique

### Comportements critiques

- [x] Réservé Superviseur + Admin SCR + Admin SAQS
- [x] Uniquement si statut = `cloture`
- [x] Statut → `valide` · `validated_by_id` renseigné
- [x] Déclenchement tâche Celery `calcul_saifi_saidi` (stub Phase 5 si formules non confirmées)
- [x] Invalidation cache Redis indicateurs concernés
- [x] `log_audit()` sur validation

### Tests (`tests/integration/test_interruption_distribution_validation.py`)

- [x] Superviseur valide interruption clôturée → 200 + `statut=valide`
- [x] BCC tente valider → 403
- [x] Validation sur interruption `en_cours` → 422
- [x] Admin SCR valide → 200

---

## Tâches transverses Sprint 3

### Backend

- [x] Schémas Pydantic alignés sur modèles `Interruption` + `InterruptionDistribution` + `PosteInterruption`
- [x] Réutiliser `paginate()`, `ApiResponse[T]`, `log_audit()` sur tous les endpoints
- [x] Seed dev : interruptions distribution minimales (`seed_interruptions.py` + `make seed-interruptions`)
- [x] Vérifier enregistrement router dans `app/api/v1/router.py` (`prefix="/interruptions/distribution"`)

### Frontend (sir-frontend · BACKLOG F3)

- [x] `shared/models/interruption.models.ts` — aligner snake_case API ↔ interfaces TS (`sir-integration`)
- [x] `features/interruptions-distribution/services/interruption-distribution.service.ts`
- [x] Liste avec filtres (région, feeder, statut, dates) + pagination Material
- [x] Formulaire création (Reactive Forms — feeder, référentiels, date apparition)
- [x] Vue détail + timeline statuts (en_cours → cloture → valide)
- [x] Actions clôture / validation (boutons conditionnels `RoleGuard` / `*sirHasRole`)
- [x] Gestion postes impactés (sous-formulaire ou modal)
- [x] Routes lazy : `/interruptions/distribution`, `/interruptions/distribution/nouveau`, `/interruptions/distribution/:id`

### Integration & QA

- [x] Rapport `docs/integration/INTEGRATION_REPORT_interruptions_distribution.md`
- [x] Couverture tests : chaque phase 3.x → tests intégration verts avant cocher
- [x] Scénarios E2E manuels : BCC saisie → clôture → Superviseur validation (script `scripts/e2e_sprint3_distribution.ps1`)

---

## Definition of done — Sprint 3

- [x] Toutes les phases 3.1 à 3.8 cochées
- [x] `make test` vert (suite complète incluant interruptions distribution)
- [x] Seeds dev interruptions chargés (`make seed-interruptions`)
- [x] Module frontend interruptions distribution fonctionnel (liste + création + détail + clôture)
- [x] Worker Celery `calcul_end` opérationnel en Docker
- [x] BACKLOG §3.1–3.8 mis à jour dans `docs/BACKLOG.md`
- [x] Formules END CRSE : confirmées SENELEC **ou** placeholder `NotImplementedError` documenté

---

---

# Sprint 4 — Interruptions Transport

> **BACKLOG Phase 4** — Cœur métier #2 · Priorité P0
>
> Prérequis : Sprint 1 + Sprint 2 + Sprint 3 ✅
>
> Modèles existants : `app/models/interruptions.py` (`InterruptionTransport`) · Router stub : `app/api/v1/interruptions/transport/router.py`
>
> **Pattern de référence :** miroir Sprint 3 (`interruption_distribution_*`) — couches schema → repository → service → router → tests intégration.
>
> **Frontend F4 :** reporté — changements UI prévus ultérieurement ; ne pas bloquer le backend.

---

## Phase 4.1 — Création interruption transport (BACKLOG §4.1)

### Fichiers à créer

- [x] `app/schemas/interruption_transport.py` — `InterruptionTransportCreate`, `InterruptionTransportResponse`, filtres ultérieurs (4.2)
- [x] `app/repositories/interruption_transport_repository.py` — insert `interruptions` + `interruptions_transport`, génération `numero_interruption`
- [x] `app/services/interruption_transport_service.py` — validation métier + RBAC périmètre national HTB
- [x] Compléter `app/api/v1/interruptions/transport/router.py`

### Endpoint

- [x] `POST /api/v1/interruptions/transport` — création interruption transport (ou OMVG via `type_direction`)

### Comportements critiques

- [x] RBAC : `DISPATCHER` + `ADMIN_DISPATCHING` uniquement (permissions `interruptions_transport:create`)
- [x] BCC / BRC / Admin SCR / Superviseur → 403 (triple RBAC : décorateur + service + tests)
- [x] Pas de scope `service_id` — périmètre national transport
- [x] Auto-génération `numero_interruption` (max+1 par année civile **et** `type_direction`)
- [x] Champs obligatoires : `date_apparition`, `equipement_transport_id`, `cause_id`, `nature_id`, `siege_id`, `signalisation_id`
- [x] Champs spécifiques transport : `source_transport_id`, `tension_kv`, `puissance_transit_mw`, `poste_ligne_id` (validation croisée avec équipement — pas de colonne dédiée en base)
- [x] Référentiels : cause / siège / signalisation → `type_reseau` ∈ {`transport`, `commun`}
- [x] `type_direction` ∈ {`transport`, `omvg`} · statut initial `en_cours` · `service_id = NULL`
- [x] Insertion ligne `interruptions_transport` (1-to-1)
- [x] `log_audit()` sur création
- [x] Dispatcher POST distribution → déjà 403 (Sprint 3) · symétrie : BCC POST transport → 403

### Tests (`tests/integration/test_interruption_transport_create.py`)

- [x] Dispatcher crée interruption transport → 201 + `statut=en_cours` + `numero_interruption` renseigné
- [x] Admin Dispatching crée interruption → 201
- [x] BCC POST transport → 403
- [x] Admin SCR POST transport → 403
- [x] Champs manquants → 422
- [x] Équipement transport inexistant / inactif → 422
- [x] `poste_ligne_id` incohérent avec `equipement_transport_id` → 422

---

## Phase 4.2 — Liste + détail interruptions transport (BACKLOG §4.2)

### Fichiers à compléter

- [x] `interruption_transport_repository.py` — list paginée, get by id avec jointures
- [x] `interruption_transport_service.py` — filtres + mapping réponse détail
- [x] Schémas — `InterruptionTransportDetailResponse`, `InterruptionTransportFilters`

### Endpoints

- [x] `GET /api/v1/interruptions/transport` — liste paginée avec filtres
- [x] `GET /api/v1/interruptions/transport/{id}` — détail complet

### Filtres liste

- [x] `type_direction` (`transport` | `omvg`)
- [x] `statut`, `date_debut`, `date_fin`
- [x] `equipement_transport_id`, `source_transport_id`

### Comportements critiques

- [x] Lecture : `DISPATCHER`, `ADMIN_DISPATCHING`, `ADMIN_SAQS` (permissions `interruptions_transport:read`)
- [x] BCC / Admin SCR → 403
- [x] Pagination `page` / `page_size` (réutiliser `paginate()`)
- [x] Détail : champs transport (`tension_kv`, `equipement_transport_id`, `source_transport_id`, `puissance_transit_mw`, `energie_non_fournie_mwh`)
- [x] Métadonnées audit : `created_by`, `created_at`, `updated_at`, `validated_by`

### Tests (`tests/integration/test_interruption_transport_list.py`, `test_interruption_transport_detail.py`)

- [x] Dispatcher GET liste → 200 + pagination
- [x] Admin SAQS GET liste → 200 (lecture seule)
- [x] BCC GET transport → 403
- [x] GET détail existant → 200 + structure complète
- [x] ID inexistant → 404

---

## Phase 4.3 — Modification / clôture transport (BACKLOG §4.3)

### Endpoints

- [x] `PUT /api/v1/interruptions/transport/{id}` — mise à jour
- [x] `PATCH /api/v1/interruptions/transport/{id}/cloturer` — clôture avec `date_remise`

### Comportements critiques — modification

- [x] Uniquement si statut = `en_cours`
- [x] Seul le créateur ou `ADMIN_DISPATCHING` peut modifier
- [x] Champs modifiables : caractérisation, observations, puissance, tension, transit, localisation, flags FM/fugitif
- [x] `log_audit()` à chaque modification

### Comportements critiques — clôture

- [x] Saisie `date_remise` obligatoire · `date_remise > date_apparition`
- [x] Calcul `duree_minutes` = différence en minutes
- [x] Statut → `cloture`
- [x] Déclenchement tâche Celery `calcul_end` adaptée transport (persistance `energie_non_fournie_mwh` / `energie_nd`)
- [x] `log_audit()` sur clôture

### Tests (`tests/integration/test_interruption_transport_update.py`, `test_interruption_transport_cloture.py`)

- [x] Créateur PUT → 200
- [x] Autre Dispatcher PUT → 403
- [x] PUT sur interruption `cloture` → 403 ou 422
- [x] Clôture `date_remise` invalide → 422
- [x] Clôture OK → 200 + `statut=cloture` + `duree_minutes` renseigné
- [x] Tâche Celery `calcul_end` enqueued (mock)

---

## Phase 4.4 — Validation transport (BACKLOG §4.4)

### Endpoint

- [x] `PATCH /api/v1/interruptions/transport/{id}/valider` — validation chef d'unité

### Comportements critiques

- [x] Réservé `ADMIN_DISPATCHING` + `ADMIN_SAQS` (permission `interruptions_transport:validate`)
- [x] Superviseur / BCC / Admin SCR → 403
- [x] Uniquement si statut = `cloture`
- [x] Statut → `valide` · `validated_by_id` renseigné
- [x] Déclenchement tâche Celery `calcul_saifi_saidi` (stub Phase 5 si formules non confirmées)
- [x] Invalidation cache Redis indicateurs concernés
- [x] `log_audit()` sur validation

### Tests (`tests/integration/test_interruption_transport_validation.py`)

- [x] Admin Dispatching valide interruption clôturée → 200 + `statut=valide`
- [x] Admin SAQS valide → 200
- [x] Dispatcher tente valider → 403
- [x] Validation sur interruption `en_cours` → 422

---

## Phase 4.5 — Interruptions OMVG (BACKLOG §4.5)

> Sous-ensemble transport — même stack, discriminant `type_direction = 'omvg'`

### Comportements critiques

- [x] Création via `POST /api/v1/interruptions/transport` avec `type_direction = 'omvg'`
- [x] Liste / détail filtrables par `type_direction=omvg`
- [x] Mêmes règles RBAC et cycle de vie que transport HTB
- [x] Numérotation séquentielle distincte par `type_direction` (transport vs omvg)

### Tests (`tests/integration/test_interruption_omvg.py`)

- [x] Dispatcher crée OMVG → 201 + `type_direction=omvg`
- [x] GET liste filtre `type_direction=omvg` → résultats cohérents
- [x] Transport et OMVG numérotés indépendamment sur la même année

---

## Tâches transverses Sprint 4

### Backend

- [x] Schémas Pydantic alignés sur `Interruption` + `InterruptionTransport`
- [x] Réutiliser `paginate()`, `ApiResponse[T]`, `log_audit()` sur tous les endpoints
- [x] Seed dev : interruptions transport/OMVG (`seed_interruptions_transport.py` + `make seed-interruptions-transport`)
- [x] Vérifier enregistrement router dans `app/api/v1/router.py` (`prefix="/interruptions/transport"`)
- [x] Symétrie RBAC : blocage explicite rôles distribution dans service transport (miroir Sprint 3)

### Frontend (sir-frontend · BACKLOG F4) — **REPORTÉ**

> Refonte UI prévue ultérieurement — ne pas démarrer F4 tant que le contrat API backend 4.1–4.4 n'est pas stable et validé par sir-qa.

- [ ] `shared/models/interruption-transport.models.ts`
- [ ] Module `features/interruptions-transport/` (liste, formulaire, détail)
- [ ] Routes lazy `/interruptions/transport`
- [ ] Rapport `docs/integration/INTEGRATION_REPORT_interruptions_transport.md`

### Integration & QA

- [x] Couverture tests : chaque phase 4.x → tests intégration verts avant cocher
- [ ] Scénario E2E manuel : Dispatcher saisie → clôture → Admin Dispatching validation (script `scripts/e2e_sprint4_transport.ps1`)

---

## Definition of done — Sprint 4

- [x] Toutes les phases 4.1 à 4.5 cochées (backend)
- [x] `make test` vert (suite complète incluant interruptions transport)
- [x] Seeds dev interruptions transport chargés (`make seed-interruptions-transport` ou `make seed-dev`)
- [x] BACKLOG §4.1–4.5 mis à jour dans `docs/BACKLOG.md`
- [x] Worker Celery `calcul_end` opérationnel pour transport (placeholder END + miroir `energie_non_fournie_mwh`)
- [ ] Frontend F4 : hors scope sprint sauf demande explicite
- [ ] E2E manuel Sprint 4 (script PowerShell) — optionnel

---

---

# Sprint 5 — Indicateurs CRSE

> **BACKLOG Phase 5** — Valeur analytique centrale · Priorité P1
>
> Prérequis : Sprint 3 + Sprint 4 ✅ (interruptions distribution + transport clôturées/validées)
>
> Modèles existants : `app/models/indicateurs.py` (`EnergieNd`, `SaifiSaidi`, `NombreClientMois`) · Router stub : `app/api/v1/indicateurs/router.py`
>
> **Existant à compléter :** `end_service.py` + `calcul_end_task` (Sprint 3) · stub `calcul_saifi_saidi_task` (Phase 3.6 / 4.4)
>
> **⚠ Bloquant métier :** formules SAIFI/SAIDI/END exactes CRSE à valider SENELEC — placeholder documenté si non confirmé (cf. `CLAUDE.md`)
>
> **Frontend F5 :** reporté — KPI dashboard Angular après contrat API 5.3–5.5 stable.

---

## Phase 5.1 — Calcul SAIFI/SAIDI (BACKLOG §5.1)

### Fichiers à créer

- [x] `app/services/saifi_saidi_service.py` — `calcul_saifi()`, `calcul_saidi()`, agrégation service → délégation → région → national
- [x] `app/repositories/saifi_saidi_repository.py` — persistance `saifi_saidi`, lecture `nombre_client_mois`, agrégation `poste_interruptions`
- [x] Compléter `app/workers/tasks/indicateurs.py` — remplacer stub `calcul_saifi_saidi_task` par implémentation réelle
- [x] Schémas `app/schemas/indicateurs.py` — réponses calcul + agrégats

### Comportements critiques

- [x] Déclenchement Celery à chaque validation interruption **distribution** (`statut=valide`)
- [x] Source données : `poste_interruptions` + `nombre_clients_touches` · dénominateur `nombre_client_mois` par service/période
- [x] Persistance table `saifi_saidi` (unicité `service_id + annee + mois`)
- [x] Exclusion interruptions force majeure (aligné END)
- [x] Formules CRSE : confirmées SENELEC **ou** placeholder `NotImplementedError` / coefficients documentés dans code
- [x] Invalidation cache Redis après calcul (cf. 5.2)

### Tests

- [x] `tests/unit/test_saifi_saidi_service.py` — `assert calcul_saifi(1000, 50000) == 0.02` (formule placeholder ou CRSE validée)
- [x] `tests/unit/test_calcul_saifi_saidi_task.py` — worker persiste `saifi_saidi` après validation mock
- [x] Force majeure → SAIFI/SAIDI = 0 ou exclusion selon règle CRSE documentée

---

## Phase 5.2 — Cache Redis indicateurs (BACKLOG §5.2)

### Fichiers à créer / compléter

- [x] `app/services/indicateurs_cache_service.py` — cache-aside get/set/invalidate
- [x] Intégrer dans tous les endpoints `/indicateurs/` (phases 5.3–5.6)

### Comportements critiques

- [x] Pattern cache-aside : lecture cache → miss → DB → set cache
- [x] Clé : `indicateurs:{type}:{region_id}:{annee}:{mois}` (aligné `end_service.invalidate_indicateurs_cache`)
- [x] TTL 1 h (3600 s)
- [x] Invalidation sur calcul END + calcul SAIFI/SAIDI (validation interruption)

### Tests

- [x] `tests/unit/test_indicateurs_cache_service.py` — hit/miss/TTL/invalidate

---

## Phase 5.4 — Indicateurs détaillés (BACKLOG §5.4)

> Implémenter **avant** le tableau de bord (5.3) — le dashboard agrège ces endpoints.

### Fichiers à compléter

- [x] `app/repositories/indicateurs_repository.py` — requêtes agrégées END / SAIFI / SAIDI
- [x] `app/services/indicateurs_service.py` — logique métier + cache 5.2
- [x] Compléter `app/api/v1/indicateurs/router.py`

### Endpoints

- [x] `GET /api/v1/indicateurs/end?annee=&mois=&region_id=`
- [x] `GET /api/v1/indicateurs/saifi?annee=&mois=&region_id=`
- [x] `GET /api/v1/indicateurs/saidi?annee=&mois=&region_id=`

### Comportements critiques

- [x] RBAC lecture : rôles avec accès indicateurs (Admin SAQS, Admin SCR, Superviseur, BRC — à confirmer seed RBAC)
- [x] Scope géographique : BCC → service · BRC → région · Admin → national
- [x] Agrégation par service / délégation / région / national (paramètre `niveau` ou déduit du rôle)
- [x] `ApiResponse[T]` + pagination si liste de services
- [x] Cache Redis (5.2) sur chaque GET

### Tests (`tests/integration/test_indicateurs_end.py`, `test_indicateurs_saifi_saidi.py`)

- [x] GET END période valide → 200 + structure
- [x] BCC accès indicateur autre service → 403
- [x] Paramètres manquants → 422

---

## Phase 5.3 — Tableau de bord (BACKLOG §5.3)

### Endpoint

- [x] `GET /api/v1/indicateurs/tableau-de-bord?periode=&region_id=`

### Comportements critiques

- [x] Retourne : `end_mois`, `saifi`, `saidi`, `nb_interruptions_actives`, `nb_interruptions_mois`
- [x] Période = mois courant par défaut (`annee` + `mois` dérivés)
- [x] Réutilise services 5.4 + comptages interruptions (distribution + transport selon périmètre)
- [x] Cache Redis agrégé (clé `indicateurs:tableau-de-bord:…`)

### Tests (`tests/integration/test_indicateurs_tableau_de_bord.py`)

- [x] Admin SAQS GET → 200 + 5 KPI présents
- [x] Scope BCC → KPI limités au service

---

## Phase 5.5 — Historique 12 mois (BACKLOG §5.5)

### Endpoint

- [x] `GET /api/v1/indicateurs/historique?type=saifi|saidi|end&annees=2&region_id=`

### Comportements critiques

- [x] Série mensuelle sur N années (défaut 1 an, max 3)
- [x] Utilisé pour graphiques de tendance (frontend F5)
- [x] Cache Redis par type + région + fenêtre temporelle

### Tests (`tests/integration/test_indicateurs_historique.py`)

- [x] GET historique SAIFI 12 mois → 200 + liste ordonnée par mois
- [x] `type` invalide → 422

---

## Phase 5.6 — Classement feeders par END (BACKLOG §5.6)

### Endpoint

- [x] `GET /api/v1/indicateurs/top-feeders?periode=&region_id=&limit=10`

### Comportements critiques

- [x] Classement feeders par END cumulée sur la période (desc)
- [x] `limit` défaut 10, max 50
- [x] Scope région / service selon RBAC
- [x] Jointure `interruptions` + `energie_nd` + `feeders`

### Tests (`tests/integration/test_indicateurs_top_feeders.py`)

- [x] GET top-feeders → 200 + liste triée END décroissant
- [x] `limit=5` → max 5 éléments

---

## Tâches transverses Sprint 5

### Backend

- [x] Seed dev : snapshots `nombre_client_mois` minimaux (`seed_indicateurs.py` + `make seed-indicateurs`)
- [x] Brancher invalidation cache depuis `end_service` + `saifi_saidi_service` (cohérence clés 5.2)
- [x] Documenter formules placeholder dans `docs/` ou commentaires `# TODO(CRSE)` si SENELEC non validé
- [x] Vérifier enregistrement router `app/api/v1/router.py` (`prefix="/indicateurs"`)

### Frontend (sir-frontend · BACKLOG F5) — **REPORTÉ**

- [ ] Sélecteurs période / région / direction
- [ ] Graphiques END, SAIFI, SAIDI avec ligne objectif CRSE
- [ ] Export Excel depuis le frontend
- [ ] Rapport `docs/integration/INTEGRATION_REPORT_indicateurs.md`

### Integration & QA

- [x] Couverture tests : chaque phase 5.x → tests verts avant cocher
- [x] Scénario E2E : interruption validée → indicateurs mis à jour (script ou manuel documenté)

---

## Definition of done — Sprint 5

- [x] Toutes les phases 5.1 à 5.6 cochées (backend)
- [x] `make test` vert (suite complète incluant indicateurs)
- [x] Seeds dev `nombre_client_mois` + données SAIFI/SAIDI de démo
- [x] BACKLOG §5.1–5.6 mis à jour dans `docs/BACKLOG.md`
- [x] Stub `calcul_saifi_saidi_task` remplacé ou placeholder CRSE documenté
- [x] Frontend F5 : hors scope sprint sauf demande explicite

---

*Dernière mise à jour : 12 Juin 2026 — Sprint 5 complet (229 tests) · Sprint 6 planifié*

---

# Sprint 6 — Rapports CRSE

> **BACKLOG Phase 6** — Obligation réglementaire CRSE · Priorité P1
>
> Prérequis : Sprint 5 ✅ (indicateurs END / SAIFI / SAIDI, tableau de bord, historique, top-feeders)
>
> **Existant :** Router stub `app/api/v1/rapports/router.py` · permission `rapports:read` (ADMIN_SAQS) · dépendances `reportlab` + `openpyxl` dans `requirements.txt` · Celery `include` référence `app.workers.tasks.rapports` (**fichier à créer**)
>
> **Réutilisation Sprint 5 :** `indicateurs_service`, `indicateurs_repository`, `GET /indicateurs/top-feeders` (phase 6.5 = intégration dans exports, pas de nouvel endpoint KPI)
>
> **⚠ Bloquant métier :** format exact des rapports CRSE (PDF / Excel) à fournir par l'équipe SAQS — implémenter avec **templates placeholder** documentés `# TODO(CRSE)` si non confirmé
>
> **Frontend F6 :** reporté — déclenchement + suivi + téléchargement Angular après contrat API 6.x stable.

---

## Phase 6.6 — Génération asynchrone (BACKLOG §6.6)

> **Implémenter en premier** — socle pour toutes les phases 6.1–6.4.

### Fichiers à créer

- [x] `app/workers/tasks/rapports.py` — tâches Celery `generer_rapport_*` (bind=True, retry)
- [x] `app/services/rapport_generation_service.py` — orchestration génération, persistance fichier, mise à jour statut
- [x] `app/repositories/rapport_repository.py` — suivi jobs (`task_id`, type, statut, chemin fichier, erreur, auteur)
- [x] `app/schemas/rapports.py` — requêtes + réponses (statut, métadonnées téléchargement)
- [x] Migration Alembic : table `rapports_generes` (ou équivalent) si stockage métadonnées en DB
- [x] Volume / répertoire stockage fichiers (`RAPPORTS_STORAGE_PATH` dans `.env` + `.env.example`)

### Comportements critiques

- [x] **Jamais** de génération PDF/Excel synchrone dans un endpoint HTTP — toujours Celery
- [x] Statuts job : `pending` → `started` → `success` | `failure`
- [x] `GET /api/v1/rapports/{task_id}/status` — progression + message d'erreur si échec
- [x] `GET /api/v1/rapports/{task_id}/download` — stream fichier (PDF ou XLSX) si `success`
- [x] RBAC : `require_permission("rapports", "read")` + scope géographique aligné indicateurs
- [x] Notification email à la fin (tâche Celery `envoi_email` ou stub documenté si Phase 8 non livrée)
- [x] Expiration fichiers générés (TTL configurable, défaut 24 h — aligné `result_expires` Celery)
- [ ] Nettoyage fichiers orphelins (tâche planifiée ou hook post-expiration — optionnel sprint)

### Tests

- [x] `tests/unit/test_rapport_generation_service.py` — transitions statut, chemin fichier, erreur worker
- [x] `tests/unit/test_generer_rapport_task.py` — worker mock, retry sur exception
- [x] `tests/integration/test_rapports_status.py` — POST déclenche → GET status `pending`/`success`

---

## Phase 6.1 — Rapport journalier (BACKLOG §6.1)

### Fichiers à compléter

- [x] `app/services/rapport_journalier_service.py` — collecte données jour (interruptions, END, feeders)
- [x] `app/repositories/rapport_journalier_repository.py` — requêtes interruptions `date_apparition = jour`
- [x] Compléter `app/api/v1/rapports/router.py`

### Endpoints

- [x] `POST /api/v1/rapports/journalier` — body : `date`, `region_id?`, `format=pdf|xlsx` → retourne `task_id`
- [x] `GET /api/v1/rapports/{task_id}/status` (cf. 6.6)
- [x] `GET /api/v1/rapports/{task_id}/download` (cf. 6.6)

### Comportements critiques

- [x] Contenu minimal : interruptions du jour, statuts, END cumulée, feeders impactés
- [x] Périmètre : distribution (+ transport si ADMIN_SAQS national — aligné Sprint 5)
- [x] Date défaut = jour courant (`Africa/Dakar`)
- [x] PDF via reportlab (template placeholder CRSE)
- [x] Déclenchement via `generer_rapport_task` (6.6)

### Tests (`tests/integration/test_rapports_journalier.py`)

- [x] POST journalier date valide → 202 + `task_id`
- [x] Paramètres manquants / date invalide → 422
- [x] BCC hors périmètre → 403

---

## Phase 6.2 — Rapport mensuel distribution (BACKLOG §6.2)

### Fichiers à créer / compléter

- [x] `app/services/rapport_mensuel_service.py` — agrégation SAIFI / SAIDI / END par région/service
- [x] `app/services/rapport_export_pdf_service.py` — rendu PDF partagé (journalier + mensuel + annuel)
- [x] `app/services/rapport_export_excel_service.py` — rendu XLSX (openpyxl)

### Endpoints

- [x] `POST /api/v1/rapports/mensuel/distribution?annee=&mois=&region_id=&format=pdf|xlsx`

### Comportements critiques

- [x] Réutilise `indicateurs_service` (END, SAIFI, SAIDI) — pas de duplication formules
- [x] Export PDF + Excel (deux formats, même `task_id` ou paramètre `format`)
- [x] Structure placeholder CRSE documentée en commentaires / `docs/` si SAQS non validé
- [x] Scope RBAC : BRC région · BCC service · Admin SAQS/SCR national

### Tests (`tests/integration/test_rapports_mensuel_distribution.py`)

- [x] POST mois valide → 202 + `task_id`
- [x] GET download après worker mock → 200 + content-type PDF ou XLSX

---

## Phase 6.5 — Classement feeders dans rapports (BACKLOG §6.5)

> Réutilise `GET /indicateurs/top-feeders` (Sprint 5.6) — **pas** de nouvel endpoint KPI.

### Comportements critiques

- [x] Section « Top feeders END » intégrée aux rapports mensuels (6.2)
- [x] Section « Top feeders END » intégrée au rapport annuel (6.4)
- [x] Paramètre `limit` (défaut 10, max 50) propagé au template PDF/Excel
- [x] Données via `indicateurs_service.get_top_feeders()` — pas de requête SQL dupliquée

### Tests

- [x] `tests/unit/test_rapport_mensuel_service.py` — mock top-feeders, vérifie présence section dans payload export

---

## Phase 6.3 — Rapport mensuel transport (BACKLOG §6.3)

### Endpoints

- [x] `POST /api/v1/rapports/mensuel/transport?annee=&mois=&format=pdf|xlsx`

### Comportements critiques

- [x] Même structure que 6.2, périmètre **HTB** (`type_direction=transport`)
- [x] END transport (energie_nd / `energie_non_fournie_mwh`) — pas de SAIFI/SAIDI distribution
- [x] RBAC : DISPATCHER / ADMIN_DISPATCHING / ADMIN_SAQS — pas d'accès BCC distribution seul
- [x] Réutilise services export PDF/Excel (6.2)

### Tests (`tests/integration/test_rapports_mensuel_transport.py`)

- [x] Admin Dispatching POST → 202
- [x] BCC POST → 403

---

## Phase 6.4 — Rapport annuel (BACKLOG §6.4)

### Endpoints

- [x] `POST /api/v1/rapports/annuel?annee=&region_id=&direction=distribution|transport|consolide&format=pdf|xlsx`

### Comportements critiques

- [x] Consolidation 12 mois — réutilise `indicateurs_service.get_historique()` (Sprint 5.5)
- [x] Tendances SAIFI / SAIDI / END + comparaison objectifs CRSE (placeholder si objectifs non seedés)
- [x] Section top-feeders annuelle (6.5) — agrégation année civile via `get_top_feeders()`
- [x] Génération asynchrone (6.6)

### Tests (`tests/integration/test_rapports_annuel.py`)

- [x] POST année valide → 202 + `task_id`
- [x] `direction` invalide → 422

---

## Tâches transverses Sprint 6

### Backend

- [x] Créer `app/workers/tasks/rapports.py` (référencé dans `celery_app.py` mais absent)
- [x] Variable env `RAPPORTS_STORAGE_PATH` + création dossier au démarrage worker
- [x] Étendre seed RBAC : rôles autorisés à générer rapports (ADMIN_SAQS, ADMIN_SCR, ADMIN_DISPATCHING, DISPATCHER, BRC, BCC, SUPERVISEUR)
- [ ] Seed dev : rapport de démo ou fixture PDF minimal pour tests intégration
- [x] Vérifier enregistrement router `app/api/v1/router.py` (`prefix="/rapports"`) — déjà présent

### Frontend (sir-frontend · BACKLOG F6) — **REPORTÉ**

- [ ] Écran déclenchement génération (type, période, format)
- [ ] Suivi progression (`task_id`, polling status)
- [ ] Téléchargement PDF / Excel
- [x] Rapport `docs/integration/INTEGRATION_REPORT_rapports.md`

### Integration & QA

- [x] Couverture tests : chaque phase 6.x → tests verts avant cocher
- [x] Scénario E2E : `scripts/e2e_sprint6_rapports.ps1` — POST journalier → poll status → download
- [ ] Validation manuelle template PDF avec équipe SAQS (checklist CRSE)

---

## Definition of done — Sprint 6

- [x] Toutes les phases 6.1 à 6.6 cochées (backend)
- [x] `make test` vert (suite complète incluant rapports) — **252 tests**
- [x] Aucune génération synchrone PDF/Excel dans les routers
- [x] BACKLOG §6.1–6.6 mis à jour dans `docs/BACKLOG.md`
- [x] Templates CRSE placeholder documentés ou spec SAQS intégrée
- [x] Frontend F6 : reporté (contrat API dans `INTEGRATION_REPORT_rapports.md`)
- [x] Seed RBAC `rapports:read` étendu (BCC, BRC, ADMIN_SCR, SUPERVISEUR)

---

# Sprint 8 — Notifications

> **BACKLOG Phase 8** — Confort opérationnel · Priorité P2
>
> Prérequis : Sprint 3 + Sprint 4 ✅ (événements interruptions) · Sprint 6 ✅ (stub email rapport prêt à remplacer)
>
> **Existant :** Modèles `Destinataire`, `SmsEnvoye`, `EmailEnvoye` (`app/models/notifications.py`) · tables en base (migration `initial_schema`) · router stub `app/api/v1/notifications/router.py` · Celery `include` `app.workers.tasks.notifications` (**stub vide**) · variables `.env` : `SMS_GATEWAY_*`, `SMTP_*`
>
> **Stub Sprint 6 :** `rapport_generation_service._notify_rapport_ready()` — log only → à brancher sur `envoi_email` (8.2)
>
> **⚠ Bloquant métier :** URL + contrat API SMS Gateway (Orange Sénégal ou équivalent) à confirmer SENELEC — mode **mock/dev** si non disponible
>
> **Frontend :** SSE/WebSocket (F2 tableau de bord temps réel) **reporté** — backend 8.4 livrable indépendamment

---

## Phase 8.3 — Gestion destinataires (BACKLOG §8.3)

> **Implémenter en premier** — socle pour 8.1 et 8.2.

### Fichiers à créer

- [x] `app/schemas/notifications.py` — `DestinataireCreate`, `DestinataireUpdate`, `DestinataireResponse`
- [x] `app/repositories/destinataire_repository.py` — CRUD + filtres `service_id`, `is_active`
- [x] `app/services/destinataire_service.py` — validation téléphone/email, scope géographique
- [x] Compléter `app/api/v1/notifications/router.py` — CRUD destinataires
- [x] Pas de migration — filtrage par `service_id` sur table `destinataires` existante (pas de groupes M2M)

### Endpoints

- [x] `GET /api/v1/notifications/destinataires` — liste paginée (`service_id?`, `is_active?`)
- [x] `POST /api/v1/notifications/destinataires` — création (nom, téléphone?, email?, `utilisateur_id?`, `service_id?`)
- [x] `GET /api/v1/notifications/destinataires/{id}`
- [x] `PATCH /api/v1/notifications/destinataires/{id}`
- [x] `DELETE /api/v1/notifications/destinataires/{id}` — soft delete (`is_active=false`)

### Comportements critiques

- [x] Au moins **téléphone ou email** requis par destinataire
- [x] RBAC : `notifications:read` + `notifications:admin` dans `seed_rbac.py`
- [x] Scope : ADMIN_SCR / ADMIN_DISPATCHING / ADMIN_SAQS national · BRC région · BCC service
- [x] Résolution destinataires par événement : filtrer actifs par `service_id`
- [x] Enum `NotificationEventType` : interruption_creee, cloturee, validee, rapport_pret, napt_soumis

### Tests

- [x] `tests/unit/test_destinataire_service.py`
- [x] `tests/integration/test_notifications_destinataires.py`

---

## Phase 8.2 — Envoi Email (BACKLOG §8.2)

### Fichiers à créer

- [x] `app/services/email_service.py` — SMTP async via `asyncio.to_thread`
- [x] `app/services/notification_template_service.py`
- [x] `app/repositories/email_repository.py`
- [x] `app/workers/tasks/notifications.py` — `envoi_email`, `envoi_email_direct`
- [x] `app/services/notification_dispatch_service.py`
- [x] `app/services/notification_trace_service.py`

### Comportements critiques

- [x] **Toujours asynchrone** via Celery
- [x] Mode mock dev si `SMTP_HOST` vide
- [x] Templates HTML `# TODO(SENELEC)`
- [x] Persistance `emails_envoyes` avec statuts
- [x] Stub `_notify_rapport_ready` remplacé
- [x] Hooks interruptions distribution + transport
- [ ] Pièce jointe PDF rapport (lien download — reporté)

### Endpoints (consultation traces)

- [x] `GET /api/v1/notifications/emails`
- [x] `GET /api/v1/notifications/emails/{id}`

### Tests

- [x] `tests/unit/test_email_service.py`
- [x] `tests/unit/test_envoi_email_task.py`
- [ ] `tests/integration/test_notifications_email.py`

---

## Phase 8.1 — Envoi SMS (BACKLOG §8.1)

### Fichiers à créer

- [x] `app/services/sms_service.py` — httpx gateway + mock dev
- [x] `app/repositories/sms_repository.py`
- [x] Tâche Celery `envoi_sms`
- [x] Intégré dans `notification_dispatch_service`

### Comportements critiques

- [x] SMS tronqué à 160 caractères
- [x] Déclenchement interruptions (distribution + transport)
- [x] Mode mock si `SMS_GATEWAY_URL` vide
- [x] Persistance `sms_envoyes`
- [x] Idempotence 5 min (marker event dans sujet/contenu)

### Endpoints (consultation traces)

- [x] `GET /api/v1/notifications/sms`
- [x] `GET /api/v1/notifications/sms/{id}`

### Tests

- [x] `tests/unit/test_sms_service.py`
- [x] `tests/unit/test_envoi_sms_task.py`
- [ ] `tests/integration/test_notifications_sms.py`

---

## Phase 8.4 — Notifications temps réel (BACKLOG §8.4)

### Fichiers à créer

- [x] `app/services/notification_stream_service.py` — Redis Pub/Sub
- [x] `GET /api/v1/notifications/stream` — SSE dans router
- [x] Schéma `NotificationEvent`

### Comportements critiques

- [x] SSE + auth JWT via query `token=`
- [x] Publication Redis à chaque dispatch
- [x] Heartbeat 30 s
- [x] Canaux par service + broadcast national
- [ ] Tests unitaires/intégration SSE (reportés)

### Tests

- [ ] `tests/unit/test_notification_stream_service.py`
- [ ] `tests/integration/test_notifications_stream.py`

---

## Tâches transverses Sprint 8

### Backend

- [x] Étendre `seed_rbac.py` : `notifications:read`, `notifications:admin`
- [x] Seed dev : `seed_notifications.py` (2 destinataires SVC-DKR-01)
- [x] `.env.example` — commentaires mock SMS/SMTP
- [x] Router enregistré — OK
- [ ] `docker compose restart worker` après déploiement (opérationnel)

### Frontend (sir-frontend · F2 temps réel) — **REPORTÉ**

- [ ] `NotificationService` — SSE `EventSource` + reconnexion
- [ ] Badge/toast sur tableau de bord (F2) — nouvelles interruptions / rapports prêts
- [ ] Rapport `docs/integration/INTEGRATION_REPORT_notifications.md`

### Integration & QA

- [x] Couverture tests principale — **264 tests** verts
- [x] Scénario E2E : `scripts/e2e_sprint8_notifications.ps1`
- [ ] Test manuel SMTP réel + gateway SMS staging

---

## Definition of done — Sprint 8

- [x] Phases 8.1 à 8.4 backend implémentées
- [x] `make test` vert — **264 tests**
- [x] Aucun envoi SMS/Email synchrone dans les routers
- [x] Stub `_notify_rapport_ready` remplacé
- [ ] BACKLOG §8.1–8.4 mis à jour
- [x] Mode mock documenté (`.env.example`)
- [x] Frontend F2 : reporté

---

*Dernière mise à jour : 15 Juin 2026 — Sprint 8 backend livré (264 tests) · E2E + tests SMS/SSE restants*
