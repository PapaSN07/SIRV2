# Rapport mensuel d'exploitation distribution (décision du 06/11/2026)

Modèle : « Analyse succincte statistiques exploitation distribution » (Service Conduite des
Réseaux, réf. PR3-INS-108-a, PDF joint au CR de la réunion de coordination DD des 29–30/10/2026),
fusionné avec le tableau des indicateurs DD (`IndicateursDD2026.xlsx`).

- Type de rapport : `mensuel_distribution` (même envoi automatique le 1er du mois à 8 h).
- Fichiers : PDF, Word et Excel produits ensemble ; l'e-mail joint les trois.
- Code : `app/repositories/rapport_mensuel_dd_repository.py` (une ligne par interruption, siège,
  entreprise, tronçon isolé), `app/services/rapport_mensuel_dd_service.py` (sections, synthèse),
  `app/services/rapport_mensuel_dd_export.py` (mise en page).
- Natures : classement du rapport hebdomadaire DD (`rapport_hebdo_dd_service.categorie`) ; HTB hors
  bilan HTA. Zone Dakar / Régions : région de l'interruption.
- Cibles : END, SAIFI, SAIDI annuels de Pilotage, au prorata des jours. **Cibles par service : à
  fournir par la DD** (graphique « END par service / cible » prêt, colonne vide en attendant).
- Hors SIR, non repris : partie BT, disponibilité des OMT (téléconduite), indicateurs commerciaux.
