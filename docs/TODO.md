# TODO — Sprint 1 : Fondations

> Légende : `[ ]` à faire · `[~]` en cours · `[x]` terminé · `[!]` bloqué
>
> Sprint suivant : Sprint 2 (Référentiels, Géo, Réseau) — débloqué quand Sprint 1 vert.

---

## Avancement global

| Phase | Titre | Statut |
| --- | --- | --- |
| 1.1 | Setup infrastructure | ✅ Terminé (CI pipeline manquant, non bloquant) |
| 1.2 | Schéma DB + Alembic | ⬜ À faire |
| 1.3 | Authentification JWT | ⬜ À faire |
| 1.4 | Système RBAC | ⬜ À faire |

---

## Phase 1.2 — Schéma DB + migration Alembic

### Modèles SQLAlchemy (`sir-backend/app/models/`)

- [ ] `utilisateurs.py` — `Utilisateur`, `Role`, `Permission`, `RolePermission`, `UserRole`
- [ ] `geo.py` — `Region`, `Delegation`, `Agence`, `Service`
- [ ] `reseau.py` — `Feeder`, `PosteSource`, `Poste`, `Troncon`, `SousFeeder`, `EquipementTransport`, `SourceTransport`, `PosteLigne`
- [ ] `interruptions.py` — `Interruption` (table centrale + discriminant `type_direction`), `InterruptionDistribution`, `InterruptionTransport`, `PosteInterruption`
- [ ] `referentiel.py` — `Cause`, `Siege`, `Signalisation`, `Nature`, `TypeEnd`
- [ ] `indicateurs.py` — `EnergieNd`, `SaifiSaidi`, `NombreClientMois`
- [ ] `napt.py` — `Napt`, `Consignation`
- [ ] `notifications.py` — `SmsEnvoye`, `EmailEnvoye`, `Destinataire`
- [ ] `audit.py` — `AuditLog`
- [ ] `app/models/__init__.py` — importer tous les modèles (nécessaire pour Alembic)

### Migration

- [ ] `make migrate msg="initial_schema"` — génère la migration
- [ ] Vérifier `make upgrade` — applique sans erreur
- [ ] Vérifier `make downgrade` — rollback propre

---

## Phase 1.3 — Authentification JWT

### Fichiers à créer

- [ ] `app/schemas/auth.py` — `LoginRequest`, `TokenResponse`, `RefreshRequest`, `MeResponse`
- [ ] `app/repositories/utilisateur_repository.py` — `get_by_login()`, `get_by_id()`
- [ ] `app/services/auth_service.py` — `login()`, `refresh()`, `logout()`, `get_current_user()`
- [ ] `app/api/v1/auth/router.py` — 4 endpoints

### Endpoints

- [ ] `POST /api/v1/auth/login` → access token (body) + refresh token (cookie HttpOnly)
- [ ] `POST /api/v1/auth/refresh` → nouveau access token
- [ ] `DELETE /api/v1/auth/logout` → blacklist JTI dans Redis
- [ ] `GET /api/v1/auth/me` → profil utilisateur connecté

### Comportements critiques

- [ ] `premiere_connexion = True` → réponse 403 avec code `FORCE_PASSWORD_CHANGE`
- [ ] JTI blacklisté dans Redis au logout (TTL = durée restante du token)
- [ ] Jamais de mot de passe dans les logs ni dans les réponses

### Tests (`tests/integration/test_auth_endpoints.py`)

- [ ] Login OK → 200 + tokens
- [ ] Login mauvais mot de passe → 401
- [ ] Login utilisateur inactif → 403
- [ ] Access token expiré → 401
- [ ] Logout puis réutilisation du token → 401
- [ ] Refresh avec cookie valide → 200

---

## Phase 1.4 — Système RBAC

### Fichiers à créer

- [ ] `app/core/deps.py` — `get_current_user()`, `require_role(*roles)`, `require_permission(ressource, action)`
- [ ] `app/repositories/rbac_repository.py` — `get_user_permissions()`, `get_user_scope()`
- [ ] `app/models/seed/seed_rbac.py` — seeding des 7 rôles et permissions initiales

### Rôles à seeder

- [ ] `BCC` — interruptions:distribution (create, read, update)
- [ ] `BRC` — interruptions:distribution (read)
- [ ] `DISPATCHER` — interruptions:transport (create, read, update)
- [ ] `ADMIN_SCR` — distribution (create, read, update, validate), admin:utilisateurs
- [ ] `ADMIN_DISPATCHING` — transport (create, read, update, validate), admin:utilisateurs
- [ ] `ADMIN_SAQS` — tout (read only)
- [ ] `SUPERVISEUR` — interruptions (read, validate scope)

### Tests (`tests/unit/test_rbac.py`)

- [ ] BCC avec `service_id` différent → 403
- [ ] BRC lecture sur sa région → 200
- [ ] Admin SCR sur endpoint transport → 403
- [ ] Admin SAQS lecture → 200, création → 403
- [ ] Dispatcher sur endpoint distribution → 403
- [ ] Superviseur validation interruption de son service → 200

---

## Tâches transverses Sprint 1

- [ ] `app/utils/pagination.py` — helper `paginate(query, page, size)` réutilisé partout
- [ ] `app/utils/audit.py` — helper `log_audit(db, table, action, user_id, data)` 
- [ ] `app/schemas/common.py` — `PaginatedResponse[T]`, `ApiResponse[T]`

---

*Dernière mise à jour : Juin 2026*
