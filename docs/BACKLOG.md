# BACKLOG — SIR (Système d'Information Réseau) · SENELEC

> Fonctionnalités à développer, priorisées et ordonnées par dépendances.
> Cocher chaque item au fur et à mesure. Mettre à jour l'état d'avancement dans CLAUDE.md.
>
> **Légende** : `[ ]` à faire · `[~]` en cours · `[x]` terminé · `[!]` bloqué

---

## Phase 1 — Socle technique
> **Priorité : P0 — Bloquant tout le reste**
> Aucun module métier ne peut démarrer avant que cette phase soit complète.

- [x] **1.1 Setup projet**
  - [x] Docker Compose : FastAPI + SQL Server 2019 + Redis 7
  - [x] Structure dossiers `sir-backend/` et `sir-frontend/` (voir CLAUDE.md §3)
  - [x] `requirements.txt` avec versions épinglées
  - [x] `.env` + `.env.example` (voir CLAUDE.md §11)
  - [ ] Pipeline CI (lint + tests automatiques)
  - [x] `Makefile` avec commandes : `make dev`, `make test`, `make migrate`

- [ ] **1.2 Schéma DB initial (migration Alembic)**
  - [ ] Tables RBAC : `roles`, `permissions`, `role_permissions`, `user_roles`
  - [ ] Table `utilisateurs` (password_hash, premiere_connexion, actif)
  - [ ] Tables géographiques : `regions`, `delegations`, `agences`, `services`
  - [ ] Tables réseau : `feeders`, `postes_sources`, `postes`, `troncons`, `sous_feeders`
  - [ ] Tables équipements transport : `equipements_transport`, `sources_transport`, `postes_lignes`
  - [ ] Table centrale `interruptions` (unifiée, avec discriminant `type_direction`)
  - [ ] Table `interruptions_distribution` (FK → interruptions)
  - [ ] Table `interruptions_transport` (FK → interruptions)
  - [ ] Table `poste_interruption` (N-N interruption ↔ postes)
  - [ ] Tables référentiels : `causes`, `sieges`, `signalisations`, `natures`, `types_end`
  - [ ] Tables calculs : `energie_nd`, `saifi_saidi`, `nombre_client_mois`
  - [ ] Tables NAPT : `napt`, `consignations`
  - [ ] Tables notifications : `smsenvoye`, `emails_envoyes`, `destinataires`
  - [ ] Table `audit_log`
  - [ ] Tester `alembic upgrade head` ET `alembic downgrade -1`

- [ ] **1.3 Authentification JWT**
  - [ ] `POST /api/v1/auth/login` → access token + refresh token (cookie HttpOnly)
  - [ ] `POST /api/v1/auth/refresh` → nouveau access token
  - [ ] `DELETE /api/v1/auth/logout` → blacklist JTI dans Redis
  - [ ] `GET /api/v1/auth/me` → profil utilisateur connecté
  - [ ] Forcer changement mot de passe si `premiere_connexion = True`
  - [ ] Tests : login OK, login KO, token expiré, logout + réutilisation token

- [ ] **1.4 Système RBAC**
  - [ ] Décorateur `@require_permission(ressource, action)`
  - [ ] Dépendance `require_role(*roles)` pour FastAPI
  - [ ] Vérification scope `service_id` / `region_id` dans les services
  - [ ] Seeding initial des rôles et permissions en base
  - [ ] Tests : BCC hors périmètre → 403, Admin SAQS → lecture OK, Admin SCR → transport → 403

- [ ] **1.5 Gestion utilisateurs (Admin)**
  - [ ] `GET /api/v1/admin/utilisateurs` (filtré par direction pour Admin SCR vs Admin Dispatching)
  - [ ] `POST /api/v1/admin/utilisateurs`
  - [ ] `PUT /api/v1/admin/utilisateurs/{id}`
  - [ ] `PATCH /api/v1/admin/utilisateurs/{id}/activer` et `/desactiver`
  - [ ] `POST /api/v1/admin/utilisateurs/{id}/reset-password`
  - [ ] Attribution de rôles + scope géographique

---

## Phase 2 — Référentiels & Réseau
> **Priorité : P0 — Données de base nécessaires à toute saisie**

- [ ] **2.1 Référentiels partagés**
  - [ ] `causes` : CRUD (type_reseau = distribution | transport | commun)
  - [ ] `sieges` : CRUD
  - [ ] `signalisations` : CRUD
  - [ ] `natures` : CRUD
  - [ ] `types_end` : CRUD
  - [ ] Endpoints : `GET /api/v1/referentiel/{ressource}` (liste) + `POST`, `PUT`, `DELETE` (Admin uniquement)
  - [ ] Mise en cache Redis (TTL 24h, invalidation sur modification)

- [ ] **2.2 Organisation géographique**
  - [ ] `GET /api/v1/geo/regions`
  - [ ] `GET /api/v1/geo/delegations?region_id=`
  - [ ] `GET /api/v1/geo/agences?delegation_id=`
  - [ ] `GET /api/v1/geo/services?agence_id=`
  - [ ] Lecture seule pour tous les rôles

- [ ] **2.3 Réseau Distribution**
  - [ ] `feeders` : CRUD complet, filtrable par poste_source_id, region
  - [ ] `postes_sources` : CRUD
  - [ ] `postes` : CRUD, association feeder
  - [ ] `troncons` : CRUD
  - [ ] `sous_feeders` : CRUD, association feeder
  - [ ] Droits : lecture pour BCC/BRC, écriture pour Admin SCR

- [ ] **2.4 Réseau Transport**
  - [ ] `equipements_transport` : CRUD (lignes HTB, transformateurs, etc.)
  - [ ] `sources_transport` : CRUD
  - [ ] `postes_lignes` : CRUD
  - [ ] Droits : lecture pour Dispatcher, écriture pour Admin Dispatching

---

## Phase 3 — Interruptions Distribution
> **Priorité : P0 — Cœur métier #1**

- [ ] **3.1 Création interruption distribution**
  - [ ] `POST /api/v1/interruptions/distribution`
  - [ ] Validation RBAC : BCC → `service_id` de l'utilisateur uniquement
  - [ ] Auto-génération `numero_interruption`
  - [ ] Champs obligatoires : date_apparition, feeder, cause, nature, siege, signalisation
  - [ ] Statut initial : `en_cours`
  - [ ] Tests : BCC hors service → 403, champs manquants → 422

- [ ] **3.2 Liste interruptions distribution**
  - [ ] `GET /api/v1/interruptions/distribution`
  - [ ] Filtres : region_id, feeder_id, statut, date_debut, date_fin
  - [ ] Pagination + tri par date_apparition DESC
  - [ ] Scope automatique : BCC voit son service, BRC voit sa région, Admin voit tout

- [ ] **3.3 Détail interruption**
  - [ ] `GET /api/v1/interruptions/distribution/{id}`
  - [ ] Inclure : postes impactés, END calculée, historique modifications

- [ ] **3.4 Modification interruption**
  - [ ] `PUT /api/v1/interruptions/distribution/{id}`
  - [ ] Uniquement si statut = `en_cours`
  - [ ] Seul le créateur ou Admin SCR peut modifier
  - [ ] Écriture dans `audit_log` à chaque modification

- [ ] **3.5 Clôture interruption**
  - [ ] `PATCH /api/v1/interruptions/distribution/{id}/cloturer`
  - [ ] Saisie `date_remise` (> date_apparition obligatoire)
  - [ ] Calcul `duree_interruption` en minutes
  - [ ] Déclenchement tâche Celery `calcul_end`
  - [ ] Statut → `cloture`

- [ ] **3.6 Validation interruption**
  - [ ] `PATCH /api/v1/interruptions/distribution/{id}/valider`
  - [ ] Réservé Superviseur + Admin SCR + Admin SAQS
  - [ ] Statut → `valide`
  - [ ] Déclenchement tâche Celery `calcul_saifi_saidi`
  - [ ] Invalidation cache Redis indicateurs concernés

- [ ] **3.7 Association postes impactés**
  - [ ] `POST /api/v1/interruptions/distribution/{id}/postes`
  - [ ] `DELETE /api/v1/interruptions/distribution/{id}/postes/{poste_id}`
  - [ ] `GET /api/v1/interruptions/distribution/{id}/postes`
  - [ ] Obligatoire avant clôture (validation dans le service)

- [ ] **3.8 Calcul END (service + worker)**
  - [ ] `end_service.py` : `calcul_end(puissance_mw, duree_h) → Decimal`
  - [ ] Exclusion interruptions force majeure
  - [ ] Application règles `types_end` / `regles_end`
  - [ ] Persistance dans table `energie_nd`
  - [ ] Mise en cache Redis clé `indicateurs:end:{region_id}:{periode}`
  - [ ] **⚠ Formules CRSE à valider avec équipe SENELEC avant implémentation**
  - [ ] Tests unitaires : `assert calcul_end(5.0, 2.0) == 10.0`, FM → 0.0

---

## Phase 4 — Interruptions Transport
> **Priorité : P0 — Cœur métier #2**

- [ ] **4.1 Création interruption transport**
  - [ ] `POST /api/v1/interruptions/transport`
  - [ ] Réservé Dispatcher (périmètre national HTB)
  - [ ] Champs spécifiques : equipement_id, source_transport_id, tension, poste_ligne_id

- [ ] **4.2 Liste + Détail interruptions transport**
  - [ ] `GET /api/v1/interruptions/transport` avec filtres adaptés
  - [ ] Scope : Dispatcher voit tout transport, Admin Dispatching idem, Admin SAQS lecture

- [ ] **4.3 Modification / Clôture**
  - [ ] Même logique que distribution, champs différents
  - [ ] Clôture déclenche calcul END transport

- [ ] **4.4 Validation transport**
  - [ ] `PATCH /api/v1/interruptions/transport/{id}/valider`
  - [ ] Validation chef d'unité (`validation_chef_unite`)
  - [ ] Réservé Admin Dispatching + Admin SAQS

- [ ] **4.5 Interruptions OMVG**
  - [ ] Sous-ensemble du transport, `type_direction = 'omvg'`
  - [ ] Mêmes endpoints, filtrage par type_direction

---

## Phase 5 — Indicateurs
> **Priorité : P1 — Valeur analytique centrale**

- [ ] **5.1 Calcul SAIFI/SAIDI**
  - [ ] `saifi_service.py` : calcul par service → délégation → région → national
  - [ ] Source : `poste_interruption` + `nombre_client_mois`
  - [ ] Tâche Celery déclenchée à chaque validation d'interruption
  - [ ] Persistance dans `saifi_saidi`
  - [ ] **⚠ Formules exactes à valider avec équipe SENELEC**
  - [ ] Tests : `assert calcul_saifi(1000, 50000) == 0.02`

- [ ] **5.2 Cache Redis indicateurs**
  - [ ] Pattern cache-aside sur tous les endpoints `/indicateurs/`
  - [ ] Clé : `indicateurs:{type}:{region_id}:{annee}:{mois}`
  - [ ] TTL 1h, invalidation sur `POST calcul_saifi_saidi`

- [ ] **5.3 Tableau de bord**
  - [ ] `GET /api/v1/indicateurs/tableau-de-bord?periode=&region_id=`
  - [ ] Retourne : END_mois, SAIFI, SAIDI, nb_interruptions_actives, nb_interruptions_mois

- [ ] **5.4 Indicateurs détaillés**
  - [ ] `GET /api/v1/indicateurs/end?annee=&mois=&region_id=`
  - [ ] `GET /api/v1/indicateurs/saifi?annee=&mois=&region_id=`
  - [ ] `GET /api/v1/indicateurs/saidi?annee=&mois=&region_id=`
  - [ ] Agrégation par service / délégation / région / national

- [ ] **5.5 Historique 12 mois**
  - [ ] `GET /api/v1/indicateurs/historique?type=saifi&annees=2`
  - [ ] Utilisé pour les graphiques de tendance

- [ ] **5.6 Classement feeders par END**
  - [ ] `GET /api/v1/indicateurs/top-feeders?periode=&region_id=&limit=10`

---

## Phase 6 — Rapports
> **Priorité : P1 — Obligation réglementaire CRSE**
> ⚠ Le format exact des rapports CRSE doit être fourni par l'équipe SAQS avant implémentation.

- [ ] **6.1 Rapport journalier**
  - [ ] `POST /api/v1/rapports/journalier` (déclenche tâche Celery)
  - [ ] `GET /api/v1/rapports/{task_id}/status` (suivi génération)
  - [ ] `GET /api/v1/rapports/{task_id}/download` (téléchargement PDF)
  - [ ] Contenu : interruptions du jour, END, statuts, feeders impactés

- [ ] **6.2 Rapport mensuel distribution**
  - [ ] SAIFI / SAIDI / END par région, format CRSE
  - [ ] Export PDF (reportlab) + Excel (openpyxl)

- [ ] **6.3 Rapport mensuel transport**
  - [ ] Même structure, périmètre HTB

- [ ] **6.4 Rapport annuel**
  - [ ] Consolidation 12 mois, tendances, comparaison objectifs

- [ ] **6.5 Classement END feeders**
  - [ ] Top / flop feeders sur période donnée

- [ ] **6.6 Génération asynchrone**
  - [ ] Toute génération passe par Celery (jamais synchrone)
  - [ ] Notification Email quand le rapport est prêt

---

## Phase 7 — NAPT
> **Priorité : P1 — Processus travaux**

- [ ] **7.1 Création NAPT**
  - [ ] `POST /api/v1/napt`
  - [ ] Champs : objet, feeder/tronçon, date prévue, demandeur, rédacteur
  - [ ] Statut initial : `brouillon`

- [ ] **7.2 Workflow NAPT**
  - [ ] Transitions : `brouillon` → `soumis` → `validé` → `exécuté` → `clôturé`
  - [ ] `PATCH /api/v1/napt/{id}/soumettre`
  - [ ] `PATCH /api/v1/napt/{id}/valider` (Superviseur/Admin)
  - [ ] `PATCH /api/v1/napt/{id}/executer`
  - [ ] `PATCH /api/v1/napt/{id}/cloturer`

- [ ] **7.3 Consignations**
  - [ ] CRUD consignations liées à un NAPT
  - [ ] Contrôleurs, validateurs

- [ ] **7.4 Liste NAPT**
  - [ ] `GET /api/v1/napt` avec filtres statut, zone, période

---

## Phase 8 — Notifications
> **Priorité : P2 — Confort opérationnel**

- [ ] **8.1 Envoi SMS**
  - [ ] Tâche Celery `envoi_sms`
  - [ ] Intégration SMS Gateway (Orange Sénégal ou API à configurer)
  - [ ] Déclenchement : nouvelle interruption, clôture, validation
  - [ ] Groupes destinataires configurables par zone et type d'événement

- [ ] **8.2 Envoi Email**
  - [ ] Tâche Celery `envoi_email`
  - [ ] Templates HTML par type d'événement
  - [ ] SMTP configurable via `.env`

- [ ] **8.3 Gestion destinataires**
  - [ ] CRUD groupes de contacts
  - [ ] Association groupe ↔ zone géographique ↔ type d'événement

- [ ] **8.4 Notifications temps réel**
  - [ ] WebSocket ou SSE sur `GET /api/v1/notifications/stream`
  - [ ] Pub/Sub Redis pour diffuser les événements
  - [ ] Mise à jour tableau de bord sans rechargement page

---

## Phase 9 — Administration
> **Priorité : P1 — Nécessaire dès la mise en production**

- [ ] **9.1 Gestion utilisateurs (frontend)**
  - [ ] Liste + filtres, activation/désactivation
  - [ ] Formulaire création/édition avec attribution rôle + scope

- [ ] **9.2 Gestion rôles et permissions**
  - [ ] Vue des rôles existants et leurs permissions
  - [ ] Attribution rôle à un utilisateur avec scope (service_id ou region_id)

- [ ] **9.3 Audit log**
  - [ ] `GET /api/v1/admin/audit-log?user_id=&table=&date_debut=`
  - [ ] Toutes mutations sensibles : interruptions, utilisateurs, NAPT, validation

- [ ] **9.4 Paramètres applicatifs**
  - [ ] Seuil durée interruption "fugitif" (ex : < 3 minutes)
  - [ ] Configuration SMS Gateway URL + clé API
  - [ ] Configuration SMTP

---

## Phase 10 — Migration des données
> **Priorité : P0 — Bloquant pour la bascule en production**

- [ ] **10.1 Audit données HFSQL**
  - [ ] Script d'analyse : doublons, NULL inattendus, valeurs hors référentiel
  - [ ] Rapport d'anomalies à corriger avant migration

- [ ] **10.2 ETL interruptions**
  - [ ] `Interruptions` + `Interruptions_Histo` + `InterruptionsTransport` + `Interruptions_OMVG`
  - [ ] → table `interruptions` unifiée + tables de détail
  - [ ] Résolution des textes VARCHAR → IDs FK (feeder, cause, siège, région…)

- [ ] **10.3 ETL référentiels**
  - [ ] `Causes` + `CausesTransport` → `causes` (champ `type_reseau`)
  - [ ] `Sieges` + `SiegesTransport` → `sieges`
  - [ ] `Signalisations` + `SignalisationsTransport` → `signalisations`

- [ ] **10.4 ETL utilisateurs**
  - [ ] Hachage bcrypt de tous les mots de passe en clair
  - [ ] Tous les utilisateurs migrés avec `premiere_connexion = True`
  - [ ] Mapping flags booléens (AdminSCR, disparcheur…) → table `user_roles`

- [ ] **10.5 ETL réseau**
  - [ ] Feeders, postes sources, postes, tronçons
  - [ ] Organisation géographique (régions, délégations, agences, services)
  - [ ] Données SIG (Noeud_SIG, Troncon_SIG, FEEDERS_SIG)

- [ ] **10.6 Validation post-migration**
  - [ ] Comparer totaux END, SAIFI, SAIDI avant/après migration
  - [ ] Vérifier counts : nb interruptions par mois sur 3 ans
  - [ ] Tests de cohérence FK (aucune FK orpheline)
  - [ ] Plan de rollback : base HFSQL en lecture seule pendant 3 mois post-bascule

---

## Frontend Angular — par module

> Développé en parallèle du backend à partir de la Phase 3.
> Chaque module frontend correspond à un module backend.

- [ ] **F0 — Core Angular**
  - [ ] `AuthService` + `JwtInterceptor` (ajout `Authorization: Bearer`)
  - [ ] `AuthGuard` + `RoleGuard`
  - [ ] `ErrorInterceptor` (401 → redirect login, 403 → page accès refusé)
  - [ ] `NgRx Store` : state utilisateur connecté, interruptions actives
  - [ ] Layout principal : sidebar + header + contenu

- [ ] **F1 — Authentification**
  - [ ] Page login
  - [ ] Page changement mot de passe obligatoire (première connexion)

- [ ] **F2 — Tableau de bord**
  - [ ] 4 cartes KPI : END mois, SAIFI, SAIDI, interruptions actives
  - [ ] Graphique interruptions 30 derniers jours (distribution vs transport)
  - [ ] Tableau dernières interruptions avec badges statut
  - [ ] Mise à jour temps réel (WebSocket ou polling 30s)

- [ ] **F3 — Interruptions Distribution**
  - [ ] Liste avec filtres + pagination
  - [ ] Formulaire création (champs conditionnels selon feeder sélectionné)
  - [ ] Formulaire modification
  - [ ] Vue détail avec timeline des phases
  - [ ] Actions clôture / validation

- [ ] **F4 — Interruptions Transport**
  - [ ] Même structure que F3, champs adaptés HTB

- [ ] **F5 — Indicateurs**
  - [ ] Sélecteurs période / région / direction
  - [ ] Graphiques END, SAIFI, SAIDI avec ligne objectif CRSE
  - [ ] Export Excel depuis le frontend

- [ ] **F6 — Rapports**
  - [ ] Déclenchement génération + suivi progression
  - [ ] Téléchargement PDF / Excel

- [ ] **F7 — NAPT**
  - [ ] Liste + workflow avec boutons d'action selon statut

- [ ] **F8 — Réseau**
  - [ ] Listes feeders, postes sources, postes (lecture + admin)

- [ ] **F9 — Administration**
  - [ ] Gestion utilisateurs avec modal création/édition
  - [ ] Attribution rôles et périmètre géographique
  - [ ] Consultation audit log

---

## Récapitulatif des priorités

| Phase | Contenu | Priorité | Dépend de |
|---|---|---|---|
| 1 | Socle technique | **P0** | — |
| 2 | Référentiels & Réseau | **P0** | Phase 1 |
| 3 | Interruptions Distribution | **P0** | Phases 1, 2 |
| 4 | Interruptions Transport | **P0** | Phases 1, 2 |
| 10 | Migration données | **P0** | Phases 1–4 (bascule finale) |
| 5 | Indicateurs | **P1** | Phases 3, 4 |
| 6 | Rapports | **P1** | Phase 5 |
| 7 | NAPT | **P1** | Phases 1, 2 |
| 9 | Administration | **P1** | Phase 1 |
| 8 | Notifications | **P2** | Phases 3, 4 |

---

*Dernière mise à jour : Juin 2026*
