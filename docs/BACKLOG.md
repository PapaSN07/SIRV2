# BACKLOG — SIR (Système d'Information Réseau) · SENELEC

> Fonctionnalités à développer, priorisées et ordonnées par dépendances.
> Cocher chaque item au fur et à mesure. Mettre à jour l'état d'avancement dans CLAUDE.md.
>
> **Légende** : `[ ]` à faire · `[~]` en cours · `[x]` terminé · `[!]` bloqué
>
> **Sprint courant :** Phases 7–9 frontend (SMS, admin avancé)
> **Sprints terminés :** Sprint 1–8 backend · Vagues frontend 0–6 ✅
> **En attente :** Phase 7 NAPT · Phase 10 migration HFSQL (scripts livrés — exécution sur données réelles en attente)

---

## Phase 1 — Socle technique
> **Priorité : P0 — Bloquant tout le reste**
> **État :** ✅ Phases 1.1–1.5 terminées (Sprint 1 + phase 1.5 Sprint 2)

- [x] **1.1 Setup projet**
  - [x] Docker Compose : FastAPI + SQL Server 2019 + Redis 7
  - [x] Structure dossiers `sir-backend/` et `sir-frontend/` (voir CLAUDE.md §3)
  - [x] `requirements.txt` avec versions épinglées
  - [x] `.env` + `.env.example` (voir CLAUDE.md §11)
  - [x] Pipeline CI (lint + tests automatiques) — `.github/workflows/ci.yml`
  - [x] `Makefile` avec commandes : `make dev`, `make test`, `make migrate`, `make seed-dev`, `make seed-rbac`, `make seed-geo`, `make seed-reseau`

- [x] **1.2 Schéma DB initial (migration Alembic)**
  - [x] Tables RBAC : `roles`, `permissions`, `role_permissions`, `user_roles`
  - [x] Table `utilisateurs` (password_hash, premiere_connexion, actif)
  - [x] Tables géographiques : `regions`, `delegations`, `agences`, `services`
  - [x] Tables réseau : `feeders`, `postes_sources`, `postes`, `troncons`, `sous_feeders`
  - [x] Tables équipements transport : `equipements_transport`, `sources_transport`, `postes_lignes`
  - [x] Table centrale `interruptions` (unifiée, avec discriminant `type_direction`)
  - [x] Table `interruptions_distribution` (FK → interruptions)
  - [x] Table `interruptions_transport` (FK → interruptions)
  - [x] Table `poste_interruption` (N-N interruption ↔ postes)
  - [x] Tables référentiels : `causes`, `sieges`, `signalisations`, `natures`, `types_end`
  - [x] Tables calculs : `energie_nd`, `saifi_saidi`, `nombre_client_mois`
  - [x] Tables NAPT : `napt`, `consignations`
  - [x] Tables notifications : `smsenvoye`, `emails_envoyes`, `destinataires`
  - [x] Table `audit_log`
  - [x] Tester `alembic upgrade head` ET `alembic downgrade -1` — migration `771d41b833c8_initial_schema.py`

- [x] **1.3 Authentification JWT**
  - [x] `POST /api/v1/auth/login` → access token + refresh token (cookie HttpOnly)
  - [x] `POST /api/v1/auth/refresh` → nouveau access token
  - [x] `DELETE /api/v1/auth/logout` → blacklist JTI dans Redis
  - [x] `GET /api/v1/auth/me` → profil utilisateur connecté
  - [x] Forcer changement mot de passe si `premiere_connexion = True`
  - [x] Tests : login OK, login KO, token expiré, logout + réutilisation token — **115 tests** (1 échec connu : `test_me_without_token_returns_401` → 403 HTTPBearer)

- [x] **1.4 Système RBAC**
  - [x] Décorateur `@require_permission(ressource, action)`
  - [x] Dépendance `require_role(*roles)` pour FastAPI
  - [x] Vérification scope `service_id` / `region_id` dans les services
  - [x] Seeding initial des rôles et permissions — script `seed_rbac.py` · exécution via `make seed-dev`
  - [x] Tests : BCC hors périmètre → 403, Admin SAQS → lecture OK, Admin SCR → transport → 403

- [x] **1.5 Gestion utilisateurs (Admin)**
  - [x] `GET /api/v1/admin/utilisateurs` (filtré par direction pour Admin SCR vs Admin Dispatching)
  - [x] `POST /api/v1/admin/utilisateurs`
  - [x] `PUT /api/v1/admin/utilisateurs/{id}`
  - [x] `PATCH /api/v1/admin/utilisateurs/{id}/activer` et `/desactiver`
  - [x] `POST /api/v1/admin/utilisateurs/{id}/reset-password`
  - [x] Attribution de rôles + scope géographique

---

## Phase 2 — Référentiels & Réseau
> **Priorité : P0 — Données de base nécessaires à toute saisie**
> **État :** ✅ Terminé (Sprint 2) · rapports intégration : `INTEGRATION_REPORT_referentiel.md`, `INTEGRATION_REPORT_geo_reseau.md`

- [x] **2.1 Référentiels partagés**
  - [x] `causes` : CRUD (type_reseau = distribution | transport | commun)
  - [x] `sieges` : CRUD
  - [x] `signalisations` : CRUD
  - [x] `natures` : CRUD
  - [x] `types_end` : CRUD
  - [x] Endpoints : `GET /api/v1/referentiel/{ressource}` (liste) + `POST`, `PUT`, `DELETE` (Admin uniquement)
  - [x] Mise en cache Redis (TTL 24h, invalidation sur modification)

- [x] **2.2 Organisation géographique**
  - [x] `GET /api/v1/geo/regions`
  - [x] `GET /api/v1/geo/delegations?region_id=`
  - [x] `GET /api/v1/geo/agences?delegation_id=`
  - [x] `GET /api/v1/geo/services?agence_id=`
  - [x] Lecture seule pour tous les rôles authentifiés
  - [x] Seed dev : `make seed-geo` · jeu complet : `make seed-dev` (RBAC + geo + réseau)

- [x] **2.3 Réseau Distribution**
  - [x] `feeders` : CRUD complet, filtrable par poste_source_id, region
  - [x] `postes_sources` : CRUD
  - [x] `postes` : CRUD, association feeder
  - [x] `troncons` : CRUD
  - [x] `sous_feeders` : CRUD, association feeder
  - [x] Droits : lecture pour BCC/BRC, écriture pour Admin SCR

- [x] **2.4 Réseau Transport**
  - [x] `equipements_transport` : CRUD (lignes HTB, transformateurs, etc.)
  - [x] `sources_transport` : CRUD
  - [x] `postes_lignes` : CRUD
  - [x] Droits : lecture pour Dispatcher, écriture pour Admin Dispatching

---

## Phase 3 — Interruptions Distribution
> **Priorité : P0 — Cœur métier #1**
> **État :** Sprint 3 en cours · modèles SQLAlchemy en place · router stub `distribution/router.py`
> **Ordre implémentation :** 3.1 → 3.2 → 3.3 → 3.7 → 3.4 → 3.5 → 3.8 → 3.6

- [x] **3.1 Création interruption distribution**
  - [x] Fichiers : `schemas/interruption_distribution.py`, `repositories/`, `services/`, compléter `distribution/router.py`
  - [x] `POST /api/v1/interruptions/distribution`
  - [x] Validation RBAC : BCC → `service_id` de l'utilisateur uniquement (scope `user_roles`)
  - [x] Auto-génération `numero_interruption` · insertion `interruptions` + `interruptions_distribution`
  - [x] Champs obligatoires : date_apparition, feeder, cause, nature, siege, signalisation
  - [x] Statut initial : `en_cours` · `type_direction = 'distribution'`
  - [x] `log_audit()` sur création · Dispatcher → 403
  - [x] Tests : BCC hors service → 403, champs manquants → 422

- [x] **3.2 Liste interruptions distribution**
  - [x] `GET /api/v1/interruptions/distribution`
  - [x] Filtres : region_id, feeder_id, statut, date_debut, date_fin
  - [x] Pagination `page` / `page_size` · tri par date_apparition DESC
  - [x] Scope automatique : BCC → son service, BRC → sa région, Admin SCR / SAQS → tout

- [x] **3.3 Détail interruption**
  - [x] `GET /api/v1/interruptions/distribution/{id}`
  - [x] Inclure : libellés jointure (feeder, cause, nature…), postes impactés, END si clôturée, métadonnées audit
  - [x] BCC hors périmètre → 403 · ID inexistant → 404

- [x] **3.7 Association postes impactés** *(avant clôture 3.5)*
  - [x] `GET /api/v1/interruptions/distribution/{id}/postes`
  - [x] `POST /api/v1/interruptions/distribution/{id}/postes`
  - [x] `DELETE /api/v1/interruptions/distribution/{id}/postes/{poste_id}`
  - [x] Uniquement si statut = `en_cours` · contrainte unicité `(interruption_id, poste_id)`
  - [x] Obligatoire avant clôture (validation dans le service — phase 3.5)

- [x] **3.4 Modification interruption**
  - [x] `PUT /api/v1/interruptions/distribution/{id}`
  - [x] Uniquement si statut = `en_cours`
  - [x] Seul le créateur ou Admin SCR peut modifier
  - [x] Écriture dans `audit_log` à chaque modification

- [x] **3.5 Clôture interruption**
  - [x] `PATCH /api/v1/interruptions/distribution/{id}/cloturer`
  - [x] Saisie `date_remise` (> date_apparition obligatoire)
  - [x] Calcul `duree_minutes` · au moins 1 poste impacté requis
  - [x] Déclenchement tâche Celery `calcul_end`
  - [x] Statut → `cloture`

- [x] **3.8 Calcul END (service + worker)**
  - [x] `app/services/end_service.py` : `calcul_end(puissance_mw, duree_h) → Decimal`
  - [x] `app/repositories/end_repository.py` — persistance `energie_nd`
  - [x] `app/workers/tasks/indicateurs.py` — tâche Celery `calcul_end(interruption_id)`
  - [x] Exclusion interruptions force majeure
  - [x] Application règles `types_end` / placeholder `REGLES_END_PAR_NATURE` (table `regles_end` absente — CRSE à valider)
  - [x] Persistance dans table `energie_nd` + miroir `interruptions_distribution.end_mwh`
  - [x] Invalidation cache Redis clé `indicateurs:end:{region_id}:{periode}`
  - [x] Tests unitaires : `calcul_end(5.0, 2.0) == 10.0`, FM → 0.0, worker mock

- [x] **3.6 Validation interruption**
  - [x] `PATCH /api/v1/interruptions/distribution/{id}/valider`
  - [x] Réservé Superviseur + Admin SCR + Admin SAQS
  - [x] Uniquement si statut = `cloture` · statut → `valide` · `validated_by_id` renseigné
  - [x] Déclenchement tâche Celery `calcul_saifi_saidi` (stub Phase 5 si formules non confirmées)
  - [x] Invalidation cache Redis indicateurs concernés

### Transverses Sprint 3

- [x] Seed dev : `seed_interruptions.py` + `make seed-interruptions`
- [x] Frontend F3 — liste, création, détail, clôture, validation, postes impactés
- [ ] Rapport `docs/integration/INTEGRATION_REPORT_interruptions_distribution.md`

---

## Phase 4 — Interruptions Transport
> **Priorité : P0 — Cœur métier #2**
> **État :** ✅ Backend terminé — Sprint 4 (4.1–4.5) · F4 frontend reporté · E2E manuel optionnel

- [x] **4.1 Création interruption transport**
  - [x] `POST /api/v1/interruptions/transport`
  - [x] Réservé Dispatcher (périmètre national HTB)
  - [x] Champs spécifiques : equipement_id, source_transport_id, tension, poste_ligne_id

- [x] **4.2 Liste + Détail interruptions transport**
  - [x] `GET /api/v1/interruptions/transport` avec filtres adaptés
  - [x] Scope : Dispatcher voit tout transport, Admin Dispatching idem, Admin SAQS lecture

- [x] **4.3 Modification / Clôture**
  - [x] Même logique que distribution, champs différents
  - [x] Clôture déclenche calcul END transport

- [x] **4.4 Validation transport**
  - [x] `PATCH /api/v1/interruptions/transport/{id}/valider`
  - [x] Validation chef d'unité (`validation_chef_unite`)
  - [x] Réservé Admin Dispatching + Admin SAQS

- [x] **4.5 Interruptions OMVG**
  - [x] Sous-ensemble du transport, `type_direction = 'omvg'`
  - [x] Mêmes endpoints, filtrage par type_direction

---

## Phase 5 — Indicateurs
> **Priorité : P1 — Valeur analytique centrale**
> **État :** ✅ Terminé — Sprint 5 backend + seeds dev + E2E indicateurs
> **Référence métier :** [docs/indicateurs_sirv2.md](indicateurs_sirv2.md) (formules, endpoints, RBAC, cache Redis)

- [x] **5.1 Calcul SAIFI/SAIDI**
  - [x] `saifi_service.py` : calcul par service → délégation → région → national
  - [x] Source : `poste_interruption` + `nombre_client_mois`
  - [x] Tâche Celery déclenchée à chaque validation d'interruption
  - [x] Persistance dans `saifi_saidi`
  - [x] **⚠ Formules exactes à valider avec équipe SENELEC** (placeholder documenté)
  - [x] Tests : `assert calcul_saifi(1000, 50000) == 0.02`

- [x] **5.2 Cache Redis indicateurs**
  - [x] Pattern cache-aside sur tous les endpoints `/indicateurs/`
  - [x] Clé : `indicateurs:{type}:{region_id}:{annee}:{mois}`
  - [x] TTL 1h, invalidation sur calcul END + SAIFI/SAIDI

- [x] **5.3 Tableau de bord**
  - [x] `GET /api/v1/indicateurs/tableau-de-bord?periode=&region_id=`
  - [x] Retourne : END_mois, SAIFI, SAIDI, nb_interruptions_actives, nb_interruptions_mois

- [x] **5.4 Indicateurs détaillés**
  - [x] `GET /api/v1/indicateurs/end?annee=&mois=&region_id=`
  - [x] `GET /api/v1/indicateurs/saifi?annee=&mois=&region_id=`
  - [x] `GET /api/v1/indicateurs/saidi?annee=&mois=&region_id=`
  - [x] Agrégation par service / délégation / région / national

- [x] **5.5 Historique 12 mois**
  - [x] `GET /api/v1/indicateurs/historique?type=saifi&annees=2`
  - [x] Utilisé pour les graphiques de tendance

- [x] **5.6 Classement feeders par END**
  - [x] `GET /api/v1/indicateurs/top-feeders?periode=&region_id=&limit=10`

---

## Phase 6 — Rapports
> **Priorité : P1 — Obligation réglementaire CRSE** · **Sprint 6**
> ⚠ Le format exact des rapports CRSE doit être fourni par l'équipe SAQS avant implémentation.

- [x] **6.1 Rapport journalier**
  - [x] `POST /api/v1/rapports/journalier` (déclenche tâche Celery)
  - [x] `GET /api/v1/rapports/{task_id}/status` (suivi génération)
  - [x] `GET /api/v1/rapports/{task_id}/download` (téléchargement PDF)
  - [x] Contenu : interruptions du jour, END, statuts, feeders impactés

- [x] **6.2 Rapport mensuel distribution**
  - [x] SAIFI / SAIDI / END par région, format CRSE (placeholder)
  - [x] Export PDF (reportlab) + Excel (openpyxl)

- [x] **6.3 Rapport mensuel transport**
  - [x] Même structure, périmètre HTB
  - [x] END transport (energie_nd / energie_non_fournie_mwh)

- [x] **6.4 Rapport annuel**
  - [x] Consolidation 12 mois, tendances, comparaison objectifs (placeholder CRSE)

- [x] **6.5 Classement END feeders**
  - [x] Top feeders intégrés au rapport mensuel distribution (paramètre `limit`, défaut 10)
  - [x] Top feeders agrégés dans rapport annuel (6.4)

- [x] **6.6 Génération asynchrone**
  - [x] Toute génération passe par Celery (jamais synchrone)
  - [x] Notification Email quand le rapport est prêt (stub Phase 8)

---

## Phase 7 — NAPT
> **Priorité : P1 — EN ATTENTE** (reporté par orchestrateur)

- [!] **7.1–7.4 NAPT** — backend partiel livré · frontend liste seule
  - [x] `POST/GET/PATCH /api/v1/napt` + workflow (soumettre, valider, exécuter, clôturer)
  - [x] `POST /api/v1/napt/{id}/consignations`
  - [~] Frontend liste + actions workflow (sans formulaire création)
  - [ ] Formulaire création · CRUD consignations UI · tests · sidebar

---

## Phase 8 — Notifications
> **Priorité : P2 — Confort opérationnel** · **Sprint 8 backend ✅**

- [x] **8.1 Envoi SMS**
  - [x] Tâche Celery `envoi_sms`
  - [x] Intégration SMS Gateway (mock dev si URL vide)
  - [x] Déclenchement : nouvelle interruption, clôture, validation
  - [x] Destinataires par `service_id` sur table `destinataires`

- [x] **8.2 Envoi Email**
  - [x] Tâches Celery `envoi_email` + `envoi_email_direct`
  - [x] Templates HTML par type d'événement (`# TODO(SENELEC)`)
  - [x] SMTP configurable via `.env` (mock dev si host vide)

- [x] **8.3 Gestion destinataires**
  - [x] CRUD `/api/v1/notifications/destinataires`
  - [x] Filtrage par `service_id` / scope RBAC

- [x] **8.4 Notifications temps réel**
  - [x] SSE `GET /api/v1/notifications/stream?token=`
  - [x] Pub/Sub Redis (`sir:notifications:service:{id}` + broadcast)
  - [x] Module SMS frontend (Phase 7 plan) : liste, envoi manuel, destinataires, emails
  - [x] `POST /api/v1/notifications/sms/send` — envoi manuel utilisateurs + destinataires

---

## Phase 9 — Administration
> **Priorité : P1 — Nécessaire dès la mise en production**

- [x] **9.1 Gestion utilisateurs (frontend)**
  - [x] Liste + filtres, activation/désactivation
  - [x] Formulaire création/édition avec attribution **multi-rôles** (`GET /admin/roles`)

- [x] **9.2 Gestion rôles et permissions**
  - [x] Vue des rôles existants et leurs permissions (`/admin/roles`)
  - [x] Attribution multi-rôles à un utilisateur

- [x] **9.3 Audit log**
  - [x] `GET /api/v1/admin/audit-log` — page `/admin/audit-log`
  - [x] Instrumentation mutations : interruptions, utilisateurs, NAPT

- [~] **9.4 Paramètres applicatifs**
  - [x] Seuil durée interruption "fugitif" (`/admin/settings`)
  - [ ] Configuration SMS Gateway URL + clé API (lecture seule — `.env`)
  - [ ] Configuration SMTP (lecture seule — `.env`)

---

## Phase 10 — Migration des données
> **Priorité : P0** — Scripts ETL livrés (`scripts/migration/`) · base HFSQL source : **SIR_ALHDL**

- [x] **10.1 Audit données HFSQL**
  - [x] `audit_hfsql.py` — doublons, NULL, orphelins, rapport JSON/CSV
  - [x] `mapping.yaml` — spécification 107 tables → 37 tables dbo

- [x] **10.2 ETL interruptions**
  - [x] `Interruptions` + `Interruptions_Histo` + `InterruptionsTransport` + `Interruptions_OMVG`
  - [x] → table `interruptions` unifiée + tables de détail
  - [x] Résolution textes VARCHAR → IDs FK (feeder, cause, siège…)

- [x] **10.3 ETL référentiels**
  - [x] `Causes` + `CausesTransport` → `causes` (`type_reseau`)
  - [x] `Sieges` + `SiegesTransport` → `sieges`
  - [x] `Signalisations` + `SignalisationsTransport` → `signalisations`

- [x] **10.4 ETL utilisateurs**
  - [x] Hachage bcrypt (`premiere_connexion = True`)
  - [x] Mapping flags → `user_roles` RBAC

- [x] **10.5 ETL réseau**
  - [x] Feeders, postes sources, postes, tronçons, sous-feeders
  - [x] Géographie (régions, délégations, agences, services)
  - [ ] Données SIG — hors périmètre v1

- [x] **10.6 Validation post-migration**
  - [x] `validate_migration.py` — END, SAIFI/SAIDI, FK orphelines, RBAC
  - [x] `runbook_cutover.md` — bascule, delta, rollback
  - [ ] Exécution go/no-go sur dump réel

---

## Frontend Angular — par module

> Développé en parallèle du backend à partir de la Phase 3.
> Chaque module frontend correspond à un module backend.
> **État :** Vagues frontend 0–6 ✅ · Phase 7 SMS ✅ · Phase 9 admin avancé ✅

- [x] **F0 — Core Angular**
  - [x] `AuthService` + intercepteurs JWT + erreurs (`error.interceptor.ts`)
  - [x] `authGuard` + `roleGuard` + `premiereConnexionGuard`
  - [x] Layout principal sidebar + topbar SSE notifications

- [x] **F1 — Authentification**
  - [x] Page login (`/login`)
  - [x] Page changement mot de passe (`/changer-mot-de-passe`)

- [x] **F-ref — Référentiels & Géo (Sprint 2)**
  - [x] Module référentiel — `/admin/referentiel`
  - [x] Module géo — cascade `/geo`
  - [x] Admin réseau distribution + transport

- [x] **F2 — Tableau de bord (Vague 4)**
  - [x] KPI END, SAIFI, SAIDI, interruptions actives
  - [x] Graphique historique SAIDI/SAIFI
  - [x] Dernières interruptions · toasts SSE (`interruption_creee`, `rapport_pret`)
  - [~] Donut répartition causes — mock (pas d'endpoint backend)

- [x] **F3 — Interruptions Distribution**
  - [x] Liste (filtres, cause/région), création, détail, modification, clôture, validation
  - [x] Routes `/interruptions/distribution/*`

- [x] **F4 — Interruptions Transport**
  - [x] Liste, création, détail, modification, clôture, validation OMVG
  - [x] Routes `/interruptions/transport/*`

- [x] **F5 — Indicateurs**
  - [x] Hub `/indicateurs` — END, SAIFI/SAIDI, historique, top feeders

- [x] **F6 — Rapports**
  - [x] Hub `/rapports` — journalier, mensuel, annuel, transport

- [!] **F7 — NAPT** — EN ATTENTE
  - [~] Liste `/napt` + actions workflow (sans création)

- [x] **F8 — Réseau**
  - [x] Admin réseau distribution + transport (feeders, postes sources, postes)
  - [ ] Tronçons, sous-feeders, postes-lignes (UI)

- [x] **F9 — Administration**
  - [x] Utilisateurs CRUD + multi-rôles via `GET /admin/roles`
  - [x] Rôles/permissions (`/admin/roles`) · audit log · paramètres app
  - [x] Module notifications SMS (`/notifications/*`)

- [x] **F-notif — Notifications (Phase 7)**
  - [x] SMS liste/envoi · destinataires CRUD · emails lecture seule

- [~] **F-assistant — Aide à la décision / Assistant ML**
  - [x] Datamart vues + tables `ml_*` / `assistant_conversations`
  - [x] Scoring P0 Celery + API `/api/v1/assistant`
  - [x] UI `/assistant` + panneau fiche interruption
  - [ ] Validation SAQS phases P1–P3 (voir `docs/ASSISTANT_ML.md`)

---

## Récapitulatif des priorités

| Phase | Contenu | Priorité | Sprint | Dépend de | État |
|---|---|---|---|---|---|
| 1 | Socle technique | **P0** | Sprint 1 (+ 1.5) | — | ✅ |
| 2 | Référentiels & Réseau | **P0** | Sprint 2 | Phase 1 | ✅ |
| 3 | Interruptions Distribution | **P0** | Sprint 3 | Phases 1, 2 | ✅ |
| 4 | Interruptions Transport | **P0** | Sprint 4 | Phases 1, 2 | ✅ backend |
| 10 | Migration données | **P0** | — | Phases 1–4 | ⬜ |
| 5 | Indicateurs | **P1** | Sprint 5 | Phases 3, 4 | ✅ |
| 6 | Rapports | **P1** | Sprint 6 | Phase 5 | ✅ |
| 7 | NAPT | **P1** | — | Phases 1, 2 | ⏸ EN ATTENTE |
| 8 | Notifications | **P2** | Sprint 8 | Phases 3, 4, 6 | ✅ |
| 9 | Administration | **P1** | — | Phase 1 | ✅ |
| 10 | Migration données | **P0** | — | Phases 1–4 | ⏸ EN ATTENTE |

---

*Dernière mise à jour : 12 Juin 2026 — vagues frontend 0–6 ✅ · SMS + admin avancé ✅ · NAPT + migration HFSQL en attente*
