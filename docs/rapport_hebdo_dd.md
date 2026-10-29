# Rapport hebdomadaire d'exploitation DD

Automatisation des modèles « Rapport Hebdo DD S39 » (Word) et « TB suivi Qualité réseau HTA et BT »
(Excel) — décision du 29/10/2026.

## Envoi

- Chaque **samedi à 8 h** (heure de Dakar), semaine du **samedi au vendredi** précédents
  (`rapport_hebdo_dd_service.semaine_samedi_vendredi`). Numéro de semaine = semaine ISO du vendredi
  (modèle : S39 du 25/09 au 01/10/2021).
- Un seul rapport **national**, envoyé à tous les destinataires actifs de Notifications, avec trois
  pièces jointes : **Word**, **Excel** (tableau de bord jour par jour) et **PDF**.
- Génération à la demande : écran Rapports → « Hebdomadaire d'exploitation DD » (Admin SCR,
  Admin SAQS) ou `POST /api/v1/rapports/hebdo-dd {"date_fin": "AAAA-MM-JJ", "format": "docx|xlsx|pdf"}`.
- Planification : `app/workers/celery_app.py` (`rapport-hebdo-dd-samedi-8h`), worker lancé avec `-B`.

## Données (HTA uniquement)

Interruptions distribution dont la **date d'apparition** est dans la semaine, **tous statuts**
(le rapport part le samedi, avant validation de toutes les interruptions).

| Catégorie du rapport | Règle SIRV2 |
|---|---|
| Réseau HTB / production (hors tableaux HTA) | cause contenant « HTB », « PRODUCTION », « BLACK START » |
| Manœuvre réseau HTA | cause contenant « Manœuvre » |
| Permanent / Semi permanent / Fugitif / Délestage incident HTA | nature du même nom |
| Travaux réseau HTA | nature Coupure et cause « Travaux » |
| Autres coupures HTA | nature Coupure (autre cause), Effacement, non renseignée |
| dont facteurs exogènes | cause Choc accidentel, Agression, Malveillance, Facteurs exogènes |

- Incidents réseaux = permanents + semi-permanents + fugitifs ; leur END inclut les délestages
  incidents HTA (comme le modèle).
- END = `interruptions_distribution.end_mwh` (kWh dans les tableaux).
- SAIFI/SAIDI semaine et cumul de l'année : `saifi_saidi_service.calculer_perimetre` (formule
  SENELEC), SAIDI affiché en h:mm:ss.
- Valeur cible : objectif END national de l'année saisi dans Pilotage (cible hebdo = annuel / 52,
  cible cumulée au prorata des jours). Sans objectif : phrase et cible omises.

## Mise en page (validée dans Claude Design le 29/10/2026)

Word et PDF : en-tête sobre (logo, Direction de la Distribution), « Semaine NN — AAAA », 4 indicateurs
clés (interruptions HTA, END, SAIFI, SAIDI) avec l'écart à S-1 (vert = baisse, ambre = hausse),
« En bref », barre segmentée des interruptions par catégorie et détail de l'END, faits marquants,
tableau par service (zéros estompés), barres du poids des services dans l'END (services qui font
80 % de l'END en violet), cartes des cumuls (END vs cible, facteurs exogènes), tableau SAIFI/SAIDI
(semaine, S-1, cumul). Palette : violet SENELEC `#5B2C6F`, lilas `#B79AC4`, orange `#F39200`,
ambre `#B86B00`, vert `#1E7B34`. Code : `construire_vue` dans `rapport_hebdo_dd_export.py`.

## Textes générés

- Introduction : amélioration / dégradation / évolution contrastée par rapport à S-1 (nombre et END),
  point saillant si un incident HTB a provoqué ≥ 20 interruptions HTA dans la journée.
- Faits majeurs : interruptions dues aux facteurs exogènes, incidents HTB, 3 plus fortes END ;
  listes Dakar / Régions (facteurs exogènes, 12 maximum par zone).

## Non repris du modèle

- **Partie BT** (nombre de défauts, temps d'attente, temps moyen de dépannage) : données hors SIR.
- Détail par niveau de tension (30 kV / 6,6 kV) des onglets masqués du classeur.

Code : `app/services/rapport_hebdo_dd_service.py` (calculs, textes), `rapport_hebdo_dd_export.py`
(Word, Excel, PDF), `app/utils/docx_simple.py` (Word sans dépendance : python-docx n'est pas dans
l'image et pip est bloqué par le proxy SENELEC), `app/repositories/rapport_hebdo_repository.py`.
