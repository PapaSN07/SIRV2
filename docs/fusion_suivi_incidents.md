# Fusion « Suivi incidents SIR » dans SIRV2

> Branche : `feat/fusion-suivi-incidents` (tirée de `origin/SIR_MSENE` le 25/11/2026).
> App source : dépôt `lamaneND/suivi-incidents-SIR`, branche `feat/retours-cheikh-seck-hta-htb` (18/11/2026).
> Objectif : une seule application. Les écrans du tableau de bord « Suivi incidents » sont réécrits dans SIRV2 (FastAPI + Angular).
>
> **Principe (25/11/2026)** : le suivi incidents intégré se base sur **SIRV2** — ses données (base `SIRV2`), ses règles (région d'exploitation du service, base clients BI_ODS, règle des 5 minutes), ses utilisateurs et ses droits. Il ne cherche pas à reproduire les chiffres de l'ancienne app. L'ancienne app reste en service jusqu'au déploiement de SIRV2, puis elle est arrêtée.

## 1. Pourquoi une réécriture et pas une fusion de code

| | Suivi incidents | SIRV2 |
|---|---|---|
| Frontend | React 19 + Vite, Tailwind, Recharts, Leaflet | Angular 17, Material, graphiques SVG maison, Leaflet |
| Backend | pandas en mémoire (~800 000 lignes, un seul worker), SQL brut | SQLAlchemy async, routers → services → repositories, Celery |
| Données | Tables SIR v1 de `IndicateursTransportDistribution` (copie rechargée chaque heure), lecture seule (`LectSIP`) | Base `SIRV2` (srv-bddomtech), alimentée par `scripts/migration/delta_periode.py` |
| Auth | LDAPS + JWT 480 min, rôles `admin` / `user` (`SIR_UserRoles`, groupe AD `SIR_Admins`) | LDAP + JWT 30 min / refresh 7 j, RBAC 8 rôles + permissions |
| Tests | 156 snapshots de non-régression (jeu figé du 15/10/2026) | ~571 tests pytest |

Le code React et le modèle « tout en mémoire » ne sont pas transposables. On reprend **les écrans et les fonctions** ; les calculs sont ceux de SIRV2.

## 2. Inventaire écran par écran

Légende : ✅ existe dans SIRV2 · 🟡 existe en partie · ❌ à créer.

| Écran Suivi incidents | Contenu | SIRV2 | Écart à combler |
|---|---|---|---|
| Barre de filtres | dates, zone Dakar/Régions, poste source, nature, cause, réseau HTB, exogène | 🟡 période + région (`/indicateurs/tableau-de-bord`) | filtres poste source, nature, cause, HTB, exogène |
| Cartes KPI (3 rangées) | interruptions / incidents, Dakar, Régions, END HTA/HTB/total, durée moyenne et cumulée, taux de localisation, SAIFI/SAIDI Dakar | 🟡 indicateurs clés du dashboard | END HTA/HTB/total, durées, taux de localisation, distinction interruption / incident |
| Vue d'ensemble | drill-down Région → Département → Commune → Localité, légende par nature, en-tête semaine Senelec | ❌ (semaine Senelec ✅ côté backend) | géographie administrative des postes, drill-down |
| Carte & évolution | carte Leaflet des incidents, série journalière | 🟡 carte des postes sans remise, historique mensuel | marqueurs agrégés par position, série journalière |
| Carte SAIFI/SAIDI | bulles par service et par poste, tableau des contributions par service | ❌ | contributions par service / poste (dénominateur commun) |
| Focus opérationnel | tableaux par poste source et par feeder | 🟡 `/indicateurs/top-feeders` | classement par poste source, contribution SAIFI/SAIDI |
| Qualité de service | barres par région | 🟡 pilotage Dakar / Régions | barres par région administrative |
| SAIFI / SAIDI | synthèse HTA/HTB/total × 3 périodes ; rapport par nature (format outil bureau, 6 décimales) ; graphique et tableau mois × nature | 🟡 synthèse ✅ (`/indicateurs/synthese-saifi-saidi`), historique ✅ | ventilation par nature, tableau mois × nature |
| Nature | répartition par nature agrégée (Incident, Travaux, Délestage) | 🟡 répartition par nature (import FIS, dashboard) | règle `NatureAgregee` / `EstIncident` à aligner |
| Localisation | taux de géolocalisation, types de correspondance, non-localisés par poste source | ❌ | statut de localisation par poste |
| Correspondances (admin) | validation manuelle poste SIR ↔ poste SIG, recensement terrain | 🟡 rapprochement Schéma / SIG / SIR (23/11) | réutiliser cet écran pour les corrections manuelles ; reprendre `MatchingManuel` et `Recensement_Postes` |
| Administration (admin) | rôles des utilisateurs, recherche AD | ✅ Administration → Utilisateurs / Rôles et droits | aucun : utilisateurs et droits de SIRV2 (permission `indicateurs:read`) |

### Organisation retenue (25/11/2026)

Un nouveau menu **« Suivi incidents »** dans SIRV2 (route `/suivi-incidents`, `loadComponent` + `roleGuard`, permission `indicateurs:read`), avec les mêmes onglets que l'ancienne app pour que ses utilisateurs retrouvent leurs repères. Les écrans d'administration rejoignent ceux qui existent déjà.

| Onglet de l'ancienne app | Dans SIRV2 | À construire |
|---|---|---|
| Barre de filtres | barre commune aux onglets | filtres poste source, nature, cause, réseau HTB (règle du 25/11), exogène |
| Vue d'ensemble + cartes KPI | onglet « Vue d'ensemble » | drill-down Région → Département → Commune → Localité ; localités |
| Carte & évolution | onglet « Carte & évolution » | carte Leaflet (existante), série journalière |
| Carte SAIFI/SAIDI | même onglet | contributions par service et par poste |
| Focus opérationnel | onglet « Focus opérationnel » | classement par poste source (feeders existants) |
| Qualité de service | onglet « Qualité de service » | barres par région |
| SAIFI / SAIDI | onglet « SAIFI / SAIDI » | synthèse (faite), tableau mois × nature, rapport par nature |
| Nature | onglet « Nature » | catégories du rapport hebdo DD |
| Localisation | onglet « Localisation » | taux de postes localisés SIG, liste des non-localisés |
| Correspondances (admin) | Administration → SIG / rapprochement Schéma-SIG-SIR | reprise des corrections manuelles et du recensement |
| Administration (admin) | Administration → Utilisateurs / Rôles et droits | rien |

## 3. Écarts dans le modèle de données SIRV2

| Besoin | État SIRV2 | Proposition |
|---|---|---|
| Cause « réseau HTB » (`Causes.CauseReseauHTB`) | absent de `causes` (`app/models/referentiel.py`) ; le rapport hebdo DD le déduit du libellé | pas de colonne : règle du rapport hebdo DD sur le libellé de la cause (décision du 25/11, §5), extraite dans une fonction partagée |
| Cause « facteur exogène » (`Causes.FacteursExogenes`) | absent | colonne booléenne `est_exogene` (Alembic), reprise depuis SIR v1 |
| Coordonnées des postes | calculées à la volée par nom de nœud SIG (`pilotage_repository`, ~l.560-615) | lien `postes.noeud_sig_id` (FK) + statut de localisation, calculés par une tâche Celery et non à chaque requête |
| Géographie administrative (département, commune, localité) | absente | table `localites` (région, département, commune, localité) reprise du fichier « Postes_Affectes_Localites », FK depuis `noeuds_sig` ou `postes` |
| Corrections manuelles (`MatchingManuel`) et recensement (`Recensement_Postes`) | partiellement couvert par le rapprochement Schéma / SIG / SIR | reprise des lignes existantes dans les tables SIRV2 du rapprochement |
| Coordonnées des services (`Localisation_Service`) | absente | colonnes lat/lon sur `services` |

## 4. Règles métier : comparaison du code (25/11/2026, hors ligne)

SIRV2 fait foi. Ce tableau sert à **expliquer** les écarts de chiffres entre l'ancienne app et SIRV2 pendant la période où les deux tournent, et à repérer ce que SIRV2 doit encore calculer (lignes ❌ « absent »).

Références : Suivi incidents `backend/app/services/saifi.py` et `chargement.py` (branche `feat/retours-cheikh-seck-hta-htb`) ; SIRV2 `app/repositories/pilotage_repository.py`, `app/services/indicateurs_service.py`, `app/services/rapport_hebdo_dd_service.py`.

| Règle | Suivi incidents | SIRV2 | Verdict |
|---|---|---|---|
| Exclusion ≤ 5 min | `round(dureeHeure × 60) ≤ 5` → exclue | `duree_minutes > 5` (`pilotage_repository.py:101`) ; reprise SIR v1 : `round(dureeHeure × 60)` (`transforms/dates.py`) | ✅ identique pour les interruptions reprises de SIR v1. ⚠️ Saisie SIRV2 : durée tronquée à la minute (`interruption_distribution_service._compute_duree_minutes`), 5 min 40 s → 5 → exclue, alors que l'outil arrondit à 6 → comptée |
| Durée SAIDI | `dureeHeure` exacte | `duree_minutes / 60` (minutes entières) | 🟡 écart d'arrondi < 30 s par interruption, négligeable |
| Interruptions comptées | toutes les lignes Dakar (durée nulle = brève) | clôturées avec date de remise (`_distribution_saifi_saidi`) | 🟡 équivalent en pratique ; une interruption en cours n'entre pas dans SIRV2 |
| Clients d'une interruption | Σ `nombreclientposteEstime` des postes, sans déduplication | Σ `COALESCE(nombre_clients_estime, nombre_clients_touches)` (`_clients_poste`) | ✅ même formule ; SIRV2 ajoute un repli sur les clients saisis |
| Dénominateur | `NombreClientMois` IDRegions 15 du mois de MAX(DateApparition), brèves comprises ; sinon dernier mois connu | même principe (`avec_duree_min=False`) ; base BI_ODS depuis le 19/11 | 🟡 **source différente** (NombreClientMois SIR v1 vs BI_ODS) : écart attendu à partir de novembre |
| Périmètre Dakar | colonne `Regions` de SIR v1 (`_dakar_mask` : nulle ou « DAKAR ») | `interruptions.region_id` déduit du service (décision 02/11) | ❌ **différent** : CLAUDE.md constate que `Regions` de SIR v1 n'est pas fiable (6 471 interruptions SDDV de 2026 rangées en Régions). Les SAIFI Dakar des deux apps ne portent pas sur les mêmes interruptions |
| Zone Régions | non calculée (pas de `PosteInterruption`) | calculée | SIRV2 va plus loin |
| Semaine Senelec | samedi → vendredi, dernière semaine terminée ; numéro = semaine ISO du vendredi (S43 2026 = 17 → 23/10) | même découpage (`periodes_synthese`) ; libellé « Semaine passée (jj/mm → jj/mm) » sans numéro | ✅ mêmes bornes ; ❌ numéro « S47 » à ajouter |
| HTA / HTB | HTB = cause marquée `Causes.CauseReseauHTB` sur les interruptions distribution | **deux définitions dans SIRV2** : synthèse = interruptions transport / OMVG (`get_synthese_saifi_saidi`) ; rapport hebdo DD = cause contenant « HTB », « PRODUCTION » ou « BLACK START » (`rapport_hebdo_dd_service.categorie`) | ✅ **décidé le 25/11** : règle du rapport hebdo DD partout (§5) ; la synthèse SAIFI/SAIDI de l'accueil est à aligner |
| Facteurs exogènes | drapeau `Causes.FacteursExogenes` | mots-clés de la cause (`rapport_hebdo_dd_service.est_exogene`) | 🟡 même idée, source différente : à aligner sur le drapeau SIR v1 |
| NatureAgregee | IDNature 3/4/5 → Incident ; 2 + cause 47 → Incident ; 1 → Travaux ; 2 sinon → Délestage | catégories du rapport hebdo DD : Permanent, Semi permanent, Fugitif, Délestage HTA, Travaux (cause « Travaux »), Manœuvre, Autres, HTB | 🟡 deux découpages différents ; le découpage du rapport hebdo DD est plus fin et validé (29/10) : le réutiliser plutôt que d'en créer un troisième |
| Durée totale (rapport par nature) | durée × nombre d'UR distinctes touchées | absent | ❌ à porter |
| Clients distincts | Σ sur (poste, UR) uniques du max de clients | absent | ❌ à porter |

## 5. Décisions à prendre (SENELEC / équipe)

Réglé par le principe du 25/11 : périmètre Dakar = région du service (SIRV2) ; données = base SIRV2 ; comptes = utilisateurs et rôles SIRV2.

**Décidé le 25/11/2026 — HTB** : une interruption distribution est « HTB » quand sa cause contient « HTB », « PRODUCTION » ou « BLACK START » (règle du rapport hebdo DD, `rapport_hebdo_dd_service.categorie`). HTA = toutes les autres. Même règle partout : filtre « réseau HTB », tuile END HTA/HTB, synthèse SAIFI/SAIDI de l'accueil (qui utilise aujourd'hui les interruptions transport / OMVG et doit être alignée).

Restent ouvertes :

1. **Lecteurs actuels** : les personnes qui n'ont qu'un accès lecture à l'ancienne app doivent avoir un compte SIRV2 avec la permission `indicateurs:read` (rôle à choisir ou à créer dans Rôles et droits).
2. **Graphiques** : SVG maison ou bibliothèque Angular (ex. ngx-echarts) ?

## 6. Comparaison des chiffres (facultative)

Pas un préalable : SIRV2 fait foi. Utile pour préparer les questions des utilisateurs qui voient des chiffres différents dans les deux apps pendant la transition.

- Références Suivi incidents : snapshots `suivi incidents/backend/tests/snapshots/` (jeux `aout_dakar`, `aout_regions`, `mars`, `mars_htb`, `mars_incident`, `mars_non_exogene`, `s1_cause_hta`, `toute_periode`) — données figées au 15/10/2026.
- SIRV2 : `GET /api/v1/indicateurs/synthese-saifi-saidi`, `/tableau-de-bord`, `/historique` sur la base `srv-bddomtech/SIRV2`.
- Collecte : `python scripts/fusion/collecter_chiffres.py`, à lancer sur le réseau SENELEC (lecture seule sur les deux API déployées, résultats dans `scripts/fusion/resultats_*.json`, ignorés par git).
- Écarts attendus avant même la collecte : périmètre Dakar (§4) et base clients BI_ODS à partir de novembre.

## 7. Plan de livraison (une PR par étape, circuit « tests avant le code »)

1. Règle HTB par la cause dans la synthèse SAIFI/SAIDI de l'accueil — **fait le 25/11/2026**.
2. Squelette : route `/suivi-incidents`, onglets vides, barre de filtres et filtres côté API.
3. Onglets sur les données existantes : SAIFI/SAIDI, Nature, Focus opérationnel, Qualité de service, Carte & évolution.
4. Géographie : migrations Alembic (§3), import des localités (« Postes_Affectes_Localites », dépôt de l'ancienne app), lien poste ↔ SIG par tâche Celery ; puis onglets Vue d'ensemble et Localisation.
5. Administration : reprise des corrections manuelles et du recensement dans le rapprochement Schéma / SIG / SIR.
6. Bascule au déploiement : recette par les utilisateurs de l'ancienne app, puis redirection de l'ancienne adresse (port 8070) vers SIRV2.
