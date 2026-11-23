# Schémas unifilaires

Les schémas unifilaires AutoCAD (PDF vectoriels : schéma RI Dakar BCC, folios régionaux) sont affichés dans
SIRV2, avec chaque poste cliquable. Depuis la fiche d'une interruption (bloc **Postes impactés → Schéma
unifilaire**), l'opérateur choisit deux postes : SIRV2 coche tous les postes situés entre les deux.

## Import d'un schéma (à chaque nouvelle version)

Sur le poste ETL SENELEC (dossier SIRV2, accès à la base) :

```
pip install "pymupdf==1.26.5" --timeout 120
python scripts\migration\import_schema_unifilaire.py "D:\Schemas\SCHEMA_RI_DAKAR_OCTOBRE_2026_BCC.pdf" --nom "Dakar (BCC)" --region Dakar
python scripts\migration\import_schema_unifilaire.py "D:\Schemas\SCHEMA_RI_DAKAR_OCTOBRE_2026_BCC.pdf" --nom "Dakar (BCC)" --region Dakar --execute
```

- Sans `--execute` : simulation (lecture du PDF, rapprochement avec les postes SIRV2, rapport CSV
  `scripts/migration/reports/schema_unifilaire_<fichier>.csv`), rien n'est écrit.
- Même `--nom` : la nouvelle version remplace l'ancienne ; les associations faites à la main sont reprises
  sur les postes de même libellé.
- `--region` : le schéma est proposé en premier aux interruptions de cette région.
- Mémoire : environ 3 Go pour le schéma de Dakar (1,7 million de traits), une minute de lecture.
- PyMuPDF (licence AGPL) n'est utilisé que par ce script, sur le poste ETL ; l'API ne lit que les données
  produites (tables `schemas_unifilaires`, `schema_unifilaire_postes`, `schema_unifilaire_tuiles`).

## Lecture du PDF (`scripts/migration/schema_unifilaire/extraction.py`)

- **Postes** : petits carrés et cercles du tracé (un symbole posé dans un autre — cellules d'un grand
  poste — n'en fait qu'un). **Organes** (IAT, flèches, triangles) : formes fermées que la ligne traverse.
- **Libellés** : lignes de texte regroupées (même sens, même taille, alignées, l'une sous l'autre), puis
  associées au poste relié par un trait de rappel, sinon au plus proche (au-dessus / au-dessous : centré
  en x ; à côté : centré en y). Les marques « CM », « C », « I », « P » et les puissances sont écartées
  (la puissance est gardée à part).
- **Graphe** : segments du tracé (hachures et dégradés écartés) ; un segment qui finit sur un symbole y
  est relié ; une extrémité posée sur un autre segment fait un raccord en T ; deux lignes qui se croisent
  sans raccord ne sont pas reliées.
- **Tuiles** : PNG 256 × 256, 1 point PDF = 2 pixels au zoom maximal (Leaflet, CRS.Simple).

Essai sur le schéma RI Dakar d'octobre 2026 : 3 490 postes, dont 3 384 nommés (97 %) ; entre « Zone de
recasement Almadies 1 » et « Ngor Lamine TALL », les 10 postes de la ligne dans l'ordre.

## Postes entre deux postes (`app/services/schema_unifilaire_graphe.py`)

1. Plus court chemin le long des lignes entre les deux postes : postes du chemin, dans l'ordre (cochés).
2. Postes en antenne : branche d'un seul poste piquée sur le chemin (folios régionaux, H61) — cochés.
3. Dérivations : branches de plusieurs postes qui ne repartent que de l'intérieur du chemin — proposées
   non cochées (au-delà de 60 postes : non proposées, à cocher poste par poste).
4. Une branche qui rejoint le réseau au-delà de l'un des deux postes n'est pas « entre » les deux.

Les postes non reliés à un poste SIRV2 sont affichés mais ne peuvent pas être ajoutés : l'Admin SCR les
relie dans **Administration → Schémas unifilaires** (clic sur le poste, recherche du poste SIRV2).

## API

| Méthode | URL | Rôle |
|---|---|---|
| GET | `/api/v1/schemas-unifilaires` | schémas importés |
| GET | `/api/v1/schemas-unifilaires/{id}/postes` | postes cliquables + poste SIRV2 |
| GET | `/api/v1/schemas-unifilaires/{id}/tuiles/{z}/{x}/{y}` | tuile PNG (204 = zone blanche) |
| POST | `/api/v1/schemas-unifilaires/{id}/entre` | postes entre deux postes |
| PUT | `/api/v1/schemas-unifilaires/{id}/postes/{poste_schema_id}` | association manuelle (Admin SCR) |
| POST | `/api/v1/interruptions/distribution/{id}/postes/lot` | ajout des postes choisis (tous feeders) |

## Rapprochement Schéma / SIG / SIR et postes à créer (23/11/2026)

Suggestion du chef de service : **Administration → Schémas unifilaires → Rapprochement Schéma / SIG / SIR**.
Une ligne par poste du schéma, trois colonnes :

| Colonne | Contenu | Actions |
|---|---|---|
| Schéma unifilaire | libellé lu sur le PDF | — |
| SIG | nœud SIG rapproché (nom, feeder, station) | « Rapprocher avec le SIG » (même nom, choix manuels gardés), Rechercher, Changer, Délier |
| SIR | poste SIRV2 relié, ou décision | Relier…, **Inactif** (hors service, ni relié ni créé), **À créer** |

« À créer » ouvre la **recherche assistée** (poste source, feeder, poste) : feeder proposé d'après le nœud
SIG rapproché, sinon le plus fréquent chez les postes voisins sur le schéma (`postes_voisins`). La proposition
va dans l'onglet **Postes à créer** (poste source, feeder, poste) ; l'Admin SCR **valide** (poste créé dans
`postes`, code saisi ou `SU000123`, service du feeder, relié aux postes des schémas de même nom marqués
« à créer ») ou **rejette** (motif obligatoire). Tout est tracé dans le journal d'audit.

- Droits : rapprochement et propositions = Admin SCR, BCC, BRC ; validation / rejet = Admin SCR.
- Tables (migration `4e5f6a7b8c9d`) : `schema_unifilaire_postes.noeud_sig_id / rapprochement_sig / statut_sir`,
  `postes_a_creer`. Une réimportation du schéma reprend les nœuds SIG choisis à la main et les décisions SIR
  (même libellé) ; relancer « Rapprocher avec le SIG » pour les rapprochements automatiques.
- Les clients d'un poste créé se renseignent ensuite dans Indicateurs → Base clients → Atelier clients.

| Méthode | URL |
|---|---|
| GET | `/api/v1/schemas-unifilaires/{id}/rapprochement?filtre=&q=&page=&size=` |
| GET | `/api/v1/schemas-unifilaires/{id}/rapprochement/compteurs` |
| POST | `/api/v1/schemas-unifilaires/{id}/rapprochement/sig` |
| PUT | `/api/v1/schemas-unifilaires/{id}/rapprochement/{poste_schema_id}/sig` · `/sir` · `/statut-sir` |
| GET | `/api/v1/schemas-unifilaires/{id}/rapprochement/{poste_schema_id}/suggestion` |
| POST | `/api/v1/schemas-unifilaires/{id}/rapprochement/{poste_schema_id}/a-creer` |
| GET | `/api/v1/schemas-unifilaires/postes-a-creer?statut=propose` |
| POST | `/api/v1/schemas-unifilaires/postes-a-creer/{id}/valider` · `/rejeter` |
| GET | `/api/v1/schemas-unifilaires/sig/noeuds?q=` |

Comparaison chiffrée et carte : `scripts/migration/export_comparaison_postes.py` (lecture seule) exporte
postes SIRV2, nœuds SIG et postes des schémas ; constat du 23/11/2026 : 54 % des postes SIR retrouvés dans le
SIG, 73 % des postes SIR rangés sur deux feeders par défaut (AIR SENEGAL 30 KV, SAUVEGARDE), 1 533 nœuds SIG
sans coordonnées.
