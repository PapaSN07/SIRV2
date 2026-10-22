# Assistant ML — anticipation pannes / travaux (distribution)

**Public** : SAQS, ADMIN_SCR, équipe SIR  
**Statut** : Phase **P0 livrée** (règles + stats) — P1/P2/P3 en attente validation SAQS  
**Principe** : module **satellite** (conseil). Ne bloque jamais clôture / validation.  
**Schéma relationnel (présentation)** : [`MODELE_ASSISTANT_ML.md`](MODELE_ASSISTANT_ML.md) · [`MODELE_ASSISTANT_ML.html`](MODELE_ASSISTANT_ML.html)

---

## Architecture livrée

| Couche | Contenu |
|---|---|
| Datamart | Vues SQL `v_ml_incidents_feeder_mois`, `v_ml_incidents_troncon_sig`, `v_ml_incidents_poste` |
| Tables | `ml_feature_snapshots`, `ml_predictions`, `assistant_conversations` |
| Scoring | `ml_scoring_service` (P0) + tâche Celery `score_feeder_risk` |
| API | `/api/v1/assistant/*` (RBAC `assistant:read` / `assistant:admin`) |
| UI | Route `/assistant` + panneau sur fiche interruption |

---

## Phases à valider avec SAQS

### P0 — Règles + statistiques (actuel)

- Score 0–100 par **feeder** sur fenêtre 90 j : fréquence, part permanentes, durée moyenne, clients touchés
- Niveaux : `low` / `medium` / `high` / `critical`
- Chat sans LLM : réponses déterministes + audit feedback

**Validation SAQS demandée** :
- [ ] Seuils de score acceptables
- [ ] Définition « permanente / semi-permanente » (codes natures)
- [ ] Exclusion force majeure / délestage / travaux du score ?

### P1 — Modèle supervisé

- Features historiques 12+ mois propres
- Cible : risque panne / besoin travaux (à définir avec SAQS)
- Algorithme candidat : LightGBM / XGBoost
- Explication des facteurs obligatoire

**Prérequis** : labels métier validés + migration ITD stable

### P2 — Spatio-temporel SIG

- Propagation risque le long des tronçons SIG / nœuds
- Matching localisation ↔ `troncons_sig` fiable

### P3 — LLM Assistant (optionnel)

- RAG sur docs métier (`MODELE_DONNEES`, procédures)
- Politique SI SENELEC obligatoire (pas de LLM externe non maîtrisé)
- L’humain reste décideur

---

## Endpoints

| Méthode | Chemin | Permission |
|---|---|---|
| GET | `/api/v1/assistant/risk` | `assistant:read` |
| GET | `/api/v1/assistant/risk/feeder/{id}` | `assistant:read` |
| GET | `/api/v1/assistant/datamart` | `assistant:read` |
| POST | `/api/v1/assistant/chat` | `assistant:read` |
| POST | `/api/v1/assistant/chat/{id}/feedback` | `assistant:read` |
| POST | `/api/v1/assistant/scoring/run` | `assistant:admin` |
| POST | `/api/v1/assistant/scoring/enqueue` | `assistant:admin` |

Job Celery : `score_feeder_risk` (horizon_days, défaut 90).

---

## Migration / seed

```powershell
cd sir-backend
$env:SIR_PROFILE="senelec"
alembic upgrade head
# puis reseeder RBAC pour permissions assistant:*
python -m scripts.run_seed_rbac
```
