# CLAUDE.md — SIR (Système d'Information Réseau) · SENELEC

> Ce fichier est lu automatiquement par Claude à chaque session.
> Il contient tout le contexte nécessaire pour travailler sur ce projet sans réexpliquer.
> **Ne pas supprimer. Mettre à jour au fur et à mesure que le projet évolue.**

---

## 1. Contexte du projet

**SIR** est l'application métier centrale de la Direction Exploitation de **SENELEC** (Société Nationale d'Électricité du Sénégal). Elle gère :
- Les **interruptions de service** du réseau électrique (coupures, délestages, indisponibilités)
- Le calcul des **indicateurs de performance** : END, SAIFI, SAIDI
- La production de **rapports** (journaliers, mensuels, annuels) pour la CRSE
- Les **NAPT** (Notes d'Autorisation de Procéder aux Travaux)
- Les **notifications SMS/Email** aux équipes d'exploitation

Deux directions sont couvertes en parallèle :
- **Distribution** : réseau MT/BT, géré par les BCC/BRC
- **Transport** : réseau HTB, géré par les Dispatchers nationaux

**Migration en cours** : WebDev + HFSQL → FastAPI + Redis + SQL Server + Angular

---

## 2. Stack technique

### Backend
| Technologie | Version | Usage |
|---|---|---|
| Python | 3.12+ | Langage principal |
| FastAPI | 0.115+ | Framework API REST |
| SQLAlchemy | 2.0+ | ORM (mode async) |
| Alembic | 1.13+ | Migrations DB |
| Pydantic | v2 | Validation + settings |
| pydantic-settings | 2.x | Variables d'environnement |
| python-jose | latest | JWT (HS256) |
| passlib[bcrypt] | latest | Hachage mots de passe |
| redis / aioredis | 5.x / 2.x | Cache + broker Celery |
| Celery | 5.x | Tâches asynchrones |
| aiomssql | latest | Driver SQL Server async |
| uvicorn | 0.30+ | Serveur ASGI |
| openpyxl | latest | Export Excel |
| reportlab | latest | Export PDF |
| pytest + httpx | latest | Tests |

### Frontend
| Technologie | Version | Usage |
|---|---|---|
| Angular | 17+ | Framework SPA |
| TypeScript | 5.x | Langage |
| Angular Material | 17+ | Composants UI |
| NgRx | 17+ | Gestion d'état |
| RxJS | 7.x | Programmation réactive |
| Chart.js + ng2-charts | 4.x | Graphiques |
| @angular/cdk | 17+ | Overlay, drag-drop |

### Infrastructure
| Technologie | Usage |
|---|---|
| SQL Server 2019+ | Base de données principale |
| Redis 7+ | Cache + broker Celery + JWT blacklist |
| Docker Compose | Environnement local |
| Alembic | Migrations versionnées |

---

## 3. Structure des répertoires

```
sir-backend/
├── app/
│   ├── core/
│   │   ├── config.py          # Settings via pydantic-settings
│   │   ├── security.py        # JWT + bcrypt
│   │   ├── database.py        # Engine SQLAlchemy async + session
│   │   └── redis.py           # Client Redis
│   ├── api/
│   │   └── v1/
│   │       ├── auth/          # Login, refresh, logout, /me
│   │       ├── reseau/        # Feeders, postes sources, postes, tronçons
│   │       ├── interruptions/ # distribution/, transport/, omvg/
│   │       ├── indicateurs/   # END, SAIFI, SAIDI, tableau-de-bord
│   │       ├── rapports/      # Génération PDF/Excel
│   │       ├── napt/          # NAPT + consignations
│   │       ├── clients/       # PosteClient, abonnés
│   │       ├── notifications/ # SMS, Email, destinataires
│   │       ├── referentiel/   # Causes, sièges, signalisations, natures
│   │       └── admin/         # Utilisateurs, rôles, paramètres
│   ├── models/                # Modèles SQLAlchemy (1 fichier = 1 domaine)
│   ├── schemas/               # Pydantic Request/Response DTOs
│   ├── services/              # Logique métier pure (pas de DB directe)
│   │   ├── end_service.py
│   │   ├── saifi_service.py
│   │   └── rapport_service.py
│   ├── workers/               # Tâches Celery
│   ├── repositories/          # Couche accès données (CRUD)
│   └── utils/                 # Fonctions partagées
├── alembic/
├── tests/
│   ├── unit/
│   └── integration/
├── .env
├── requirements.txt
└── docker-compose.yml

sir-frontend/
├── src/app/
│   ├── core/
│   │   ├── auth/              # AuthService, JWT interceptor
│   │   ├── guards/            # AuthGuard, RoleGuard
│   │   └── services/          # HttpService, ErrorService
│   ├── shared/
│   │   ├── components/        # DataTable, Modal, Charts, Loading
│   │   └── models/            # Interfaces TypeScript partagées
│   └── features/              # Modules lazy-loaded
│       ├── auth/
│       ├── tableau-de-bord/
│       ├── interruptions/
│       │   ├── distribution/
│       │   └── transport/
│       ├── indicateurs/
│       ├── rapports/
│       ├── napt/
│       ├── reseau/
│       ├── clients/
│       └── administration/
```

---

## 4. Base de données

### Schémas SQL Server
| Schéma | Contenu |
|---|---|
| `dbo` | Tables métier principales |
| `referentiel` | Causes, sièges, signalisations, natures, types |
| `geo` | Régions, délégations, agences, services |
| `sig` | Données SIG importées (Troncon_SIG, Noeud_SIG…) |
| `staging` | Tables temporaires d'import (JAMAIS en prod) |
| `rapports` | Vues SQL et tables agrégées |

### Tables clés (schéma cible refactorisé)
```
interruptions               # Table centrale unifiée (remplace 4 tables HFSQL)
interruptions_distribution  # Détails propres à la distribution (FK → interruptions)
interruptions_transport     # Détails propres au transport (FK → interruptions)
feeders
postes_sources
postes
troncons
sous_feeders
utilisateurs                # password_hash UNIQUEMENT, jamais mdp en clair
roles                       # BCC, BRC, DISPATCHER, ADMIN_SCR, ADMIN_DISPATCHING, ADMIN_SAQS, SUPERVISEUR
permissions                 # ressource + action
role_permissions            # FK roles + permissions
user_roles                  # FK utilisateurs + roles + scope_service_id
energie_nd                  # Résultats calculs END persistés
saifi_saidi                 # Résultats calculs SAIFI/SAIDI persistés
poste_interruption          # Association N-N interruption ↔ postes impactés
napt
consignations
causes                      # Unifié distribution+transport (champ type_reseau)
sieges                      # Unifié
signalisations              # Unifié
natures
types_end
regions, delegations, agences, services
audit_log                   # Toutes les mutations importantes horodatées
```

### Règles de schéma importantes
- **Jamais de mot de passe en clair** — toujours `bcrypt` dans `password_hash`
- **Date + Heure toujours fusionnées** — `DATETIME2` unique, pas deux colonnes séparées
- **Toujours des FK** — pas de noms en VARCHAR à la place d'IDs
- **Référentiels unifiés** — une seule table `causes` avec `type_reseau IN ('distribution', 'transport', 'commun')`
- **Audit log** sur toutes les tables sensibles (interruptions, utilisateurs, napt)

---

## 5. RBAC — Rôles et permissions

### Rôles
| Rôle | Direction | Périmètre |
|---|---|---|
| `BCC` | Distribution | Son agence/service |
| `BRC` | Distribution | Sa région |
| `DISPATCHER` | Transport | National HTB |
| `ADMIN_SCR` | Distribution | National distribution |
| `ADMIN_DISPATCHING` | Transport | National transport |
| `ADMIN_SAQS` | Toutes | National |
| `SUPERVISEUR` | Selon service | Son service |

### Règles RBAC critiques
- Un **BCC** ne peut créer/modifier que des interruptions de **son `service_id`**
- Un **BRC** voit toutes les interruptions de **sa `region_id`**
- Un **Dispatcher** ne voit que les interruptions **transport**
- Un **Admin SCR** ne peut PAS accéder aux données transport
- Un **Admin SAQS** a accès en **lecture seule** sur tout (pas de création/modification)
- La **validation** d'une interruption est réservée aux Superviseurs et Admins
- Le **scope** est stocké dans `user_roles.scope_service_id`

### Implémentation
```python
# Backend : décorateur de permission
@require_permission("interruptions_distribution", "create")

# Vérification de scope dans le service
if current_user.role == "BCC" and interruption.service_id != current_user.service_id:
    raise HTTPException(403, "Hors périmètre")
```

---

## 6. Règles métier — Calcul des indicateurs

### END (Énergie Non Distribuée)
```
END (MWh) = Puissance_Coupée (MW) × Durée_Interruption (h)
```
**Règles d'exclusion et de pondération :**
- Les interruptions de **force majeure** sont exclues du calcul END imputable
- Le type d'END est déterminé par la table `types_end` + `regles_end`
- L'END est calculée **par interruption** à sa clôture/validation
- Elle est stockée dans la table `energie_nd` et mise en cache Redis (TTL 1h)
- **⚠ Les formules exactes de pondération CRSE doivent être confirmées avec l'équipe SENELEC avant implémentation**

### SAIFI (System Average Interruption Frequency Index)
```
SAIFI = Σ(Nombre clients interrompus) / Nombre total clients de référence
```
**⚠ La formule de base est connue. Les règles d'exclusion et de pondération CRSE doivent être confirmées avec l'équipe SENELEC avant implémentation.**

### SAIDI (System Average Interruption Duration Index)
```
SAIDI = Σ(Nombre clients interrompus × Durée interruption en minutes) / Nombre total clients
```
**⚠ Même réserve que SAIFI — pondérations CRSE à valider.**

**Source des clients** : table `nombre_client_mois` (snapshot mensuel par service)
**Périmètre** : calculé par service, délégation, région, et national
**Déclenchement** : tâche Celery asynchrone à chaque validation d'interruption

---

## 7. Redis — Utilisation

| Clé | Usage | TTL |
|---|---|---|
| `indicateurs:{type}:{region_id}:{periode}` | Cache END/SAIFI/SAIDI | 1h, invalidé sur validation |
| `jwt:blacklist:{token_jti}` | Tokens révoqués (logout) | Durée restante du token |
| `celery:broker` | File de tâches async | Jusqu'à consommation |
| `celery:results:{task_id}` | Résultats calculs | 24h |
| `ratelimit:{user_id}` | Rate limiting API | 1 min glissante |

**Pattern cache-aside** : lire Redis → si miss → calculer DB → écrire Redis → retourner

---

## 8. Conventions de code

### Python (Backend)
- **snake_case** pour tout : variables, fonctions, fichiers, colonnes DB
- **Type hints obligatoires** sur toutes les fonctions
- **Async/await** partout (SQLAlchemy async, Redis async)
- **Pas de logique métier dans les routers** — tout dans les services
- **Pas d'accès DB direct dans les services** — passer par les repositories
- **Schéma de réponse explicite** sur chaque endpoint (pas de `dict` générique)
- Un fichier de modèle = un domaine (ex: `models/interruptions.py` contient `Interruption`, `InterruptionDistribution`, `InterruptionTransport`)

```python
# Structure d'un endpoint standard
@router.post("/", response_model=InterruptionResponse, status_code=201)
async def create_interruption(
    body: InterruptionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(require_role("BCC", "BRC")),
) -> InterruptionResponse:
    return await interruption_service.create(db, body, current_user)
```

### TypeScript (Frontend)
- **camelCase** pour variables et fonctions, **PascalCase** pour classes et interfaces
- **Interfaces** pour tous les modèles de données (pas de `any`)
- **Services** pour tous les appels HTTP (jamais de `HttpClient` dans les composants)
- **NgRx** pour l'état global (interruptions en cours, utilisateur connecté, indicateurs)
- **Lazy loading** obligatoire sur tous les modules `features/`
- **RoleGuard** sur toutes les routes sensibles

```typescript
// Modèle TypeScript — toujours typer explicitement
export interface Interruption {
  id: number;
  numeroInterruption: number;
  typeDirection: 'distribution' | 'transport' | 'omvg';
  statut: 'en_cours' | 'cloture' | 'valide' | 'archive';
  dateApparition: string; // ISO 8601
  dateRemise?: string;
  dureeInterruption?: number; // en minutes
  // ...
}
```

### SQL / Alembic
- **Toujours utiliser Alembic** pour modifier le schéma — jamais de DDL manuel
- **Nommer les migrations** de façon explicite : `add_audit_log_table`, `unify_interruptions`
- **Tester les migrations** `upgrade` ET `downgrade` avant merge

### Conventions API REST
- URLs en **noms pluriels** : `/interruptions/`, `/feeders/`, `/utilisateurs/`
- Versionnage obligatoire : `/api/v1/`
- Réponse enveloppée : `{"status": "success"|"error", "data": ..., "error": null}`
- Toutes les listes sont **paginées** : `?page=1&size=20`, réponse avec `total`, `page`, `size`, `items`
- Déclarer les routes **statiques avant les routes dynamiques** : `/by-date/` avant `/{id}`

---

## 9. Authentification

- **JWT HS256** avec `python-jose`
- **Access token** : TTL 30 minutes
- **Refresh token** : TTL 7 jours, stocké en cookie HttpOnly
- **Logout** : JTI du token ajouté à la blacklist Redis (TTL = durée restante)
- **Première connexion** : forcer le changement de mot de passe (`premiere_connexion = True`)
- **Jamais de mot de passe** dans les logs ou les réponses API

---

## 10. Tests

### Structure
```
tests/
├── unit/
│   ├── test_end_service.py      # Calculs END (priorité haute)
│   ├── test_saifi_service.py    # Calculs SAIFI/SAIDI
│   └── test_rbac.py             # Règles de permissions
└── integration/
    ├── test_auth_endpoints.py
    ├── test_interruptions_api.py
    └── test_indicateurs_api.py
```

### Cas de test obligatoires pour les calculs
```python
# END
assert calcul_end(puissance_mw=5.0, duree_h=2.0) == 10.0
assert calcul_end_force_majeure(...) == 0.0  # Exclusion FM

# SAIFI
assert calcul_saifi(clients_interrompus=1000, total_clients=50000) == 0.02

# RBAC
assert bcc_ne_peut_pas_valider_interruption()
assert admin_scr_ne_voit_pas_transport()
assert bcc_ne_voit_pas_autre_service()
```

---

## 11. Variables d'environnement (.env)

```env
# Base de données
DATABASE_URL=mssql+aiomssql://user:password@localhost/SIR

# Redis
REDIS_URL=redis://localhost:6379/0

# JWT
SECRET_KEY=<clé_aléatoire_256bits>
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# Celery
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2

# App
ENVIRONMENT=development  # development | staging | production
API_VERSION=v1
CORS_ORIGINS=http://localhost:4200

# SMS Gateway (à configurer)
SMS_GATEWAY_URL=
SMS_GATEWAY_API_KEY=

# Email
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
```

---

## 12. Vocabulaire métier (lexique)

| Terme | Définition |
|---|---|
| **Interruption** | Coupure ou indisponibilité de service électrique |
| **END** | Énergie Non Distribuée (MWh) = pertes dues aux interruptions |
| **SAIFI** | Fréquence moyenne d'interruption par client |
| **SAIDI** | Durée moyenne d'interruption par client |
| **CRSE** | Commission de Régulation du Secteur de l'Énergie (régulateur sénégalais) |
| **BCC** | Bureau de Conduite Centralisée (opérateur distribution) |
| **BRC** | Bureau Régional de Conduite (opérateur régional distribution) |
| **Dispatcher** | Opérateur réseau transport HTB |
| **NAPT** | Note d'Autorisation de Procéder aux Travaux |
| **Feeder** | Départ MT depuis un poste source |
| **Poste source** | Poste de transformation HTB/MT |
| **MT** | Moyenne Tension (distribution) |
| **BT** | Basse Tension (distribution) |
| **HTB** | Haute Tension B (transport, ≥ 63 kV) |
| **OMVG** | Organisation pour la Mise en Valeur du fleuve Gambie (réseau interconnecté) |
| **Tronçon** | Section de ligne entre deux nœuds du réseau |
| **Nœud** | Point de connexion du réseau (poste, jonction…) |
| **SIG** | Système d'Information Géographique |
| **Délestage** | Coupure programmée (≠ panne) |
| **Fugitif** | Interruption très courte (< seuil défini) |
| **Permanent** | Interruption longue nécessitant intervention |
| **Semi-permanent** | Catégorie intermédiaire |
| **Siège** | Localisation physique de l'origine de la panne |
| **Signalisation** | Mode de détection de la panne |
| **Nature** | Classification de l'interruption (travaux, incident, manœuvre…) |

---

## 13. Points d'attention critiques

1. **Calculs END/SAIFI/SAIDI** : les formules exactes avec pondérations CRSE doivent être **validées avec l'équipe SENELEC** avant d'implémenter les services. Ne jamais supposer.

2. **Scope RBAC** : un BCC ne doit JAMAIS voir les données d'un autre service. Vérification double : dans le service Python ET dans les requêtes SQL (clause `WHERE service_id = :user_service_id`).

3. **Migration des données** : le schéma HFSQL source a ~65 tables avec des données dénormalisées (texte à la place d'IDs). Les scripts ETL doivent être testés sur un dump réel avant bascule.

4. **Mots de passe** : la table `Utilisateurs` HFSQL a des mots de passe en clair. À la migration, imposer un reset obligatoire à la première connexion (`premiere_connexion = True`).

5. **Performance** : les calculs SAIFI/SAIDI sur 12 mois peuvent être lourds. Toujours passer par Celery + cache Redis. Jamais de calcul synchrone dans un endpoint.

6. **Rapports CRSE** : le format exact des rapports réglementaires doit être fourni par l'équipe SAQS. Ne pas inventer le format.

---

## 14. Décisions structurantes

> Le backlog détaillé est dans [BACKLOG.md](BACKLOG.md). Ce tableau ne contient que les décisions d'architecture non dérivables du code.

| Date | Décision | Statut |
|---|---|---|
| Juin 2026 | Stack : FastAPI + SQL Server 2019+ + Redis 7 + Angular 17+ | Validé |
| Juin 2026 | Table `interruptions` unifiée avec discriminant `type_direction` (remplace 4 tables HFSQL) | Validé |
| Juin 2026 | Référentiels unifiés : une seule table `causes` avec champ `type_reseau` | Validé |
| Juin 2026 | Scope RBAC stocké dans `user_roles.scope_service_id` | Validé |
| Juin 2026 | Mode de migration : Big Bang vs Progressif | **En attente** |
| — | Formules de pondération END/SAIFI/SAIDI (règles CRSE) | **À valider avec SENELEC** |
| — | Format rapports réglementaires CRSE | **À fournir par équipe SAQS** |

---

*Dernière mise à jour : Juin 2026 — Mettre à jour uniquement pour les décisions structurantes.*
