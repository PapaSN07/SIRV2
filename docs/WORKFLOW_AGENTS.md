# Workflow des agents SIRV2

Objectif : aucune livraison n'arrive sur le serveur SENELEC sans être passée par les mêmes contrôles.
Les agents sont définis dans `.claude/agents/` ; l'orchestrateur applique ce document.

## L'équipe : 5 agents permanents, 3 spécialistes

| Agent | Rôle | Écrit du code ? |
|---|---|---|
| **sir-orchestrateur** | état du projet, plan, portes de contrôle, verdict PRÊT / NON PRÊT | non |
| **sir-backend** | FastAPI, services, repositories, Alembic, Celery | oui |
| **sir-frontend** | Angular : écrans, services HTTP, modèles | oui |
| **sir-qa** | tests, contrôles SQL Server, build, non-régression | oui (tests) |
| **sir-integration** | contrat API ↔ écran, RBAC des deux côtés | non (rapport) |
| sir-migration | données SIR v1 → SIRV2, scripts de correction | oui (scripts) |
| sir-securite | auth, droits, fichiers, secrets, dépendances | non (rapport) |
| sir-design | captures du build, charte, ergonomie | non (rapport) |

## Cycle d'une demande

```
Demande (utilisateur, SENELEC)
  │
  ▼
sir-orchestrateur ── classe la demande (backend / frontend / données / sécurité) et fixe les portes
  │
  ├─► sir-backend ──► sir-qa (pytest + dialecte mssql) ──┐
  ├─► sir-frontend ─► sir-qa (build + icônes) ───────────┤
  ├─► sir-migration ► simulation lue ────────────────────┤
  │                                                      ▼
  │                                         sir-integration (contrat, RBAC)
  │                                                      │
  │                           sir-design (si écran) · sir-securite (si droits)
  │                                                      │
  ▼                                                      ▼
sir-orchestrateur ── toutes les portes vertes ? ── PRÊT → commit, push (SIR_MSENE, fix/audit-securite)
                                             └── NON PRÊT → retour à l'agent fautif
  │
  ▼
Déploiement serveur (consignes une par ligne) → vérification à l'écran → données (simulation, sauvegarde, exécution)
```

## Portes de contrôle

| Type | Porte | Qui |
|---|---|---|
| Backend | `pytest -q` sans échec ; toute requête nouvelle compilée en mssql ; ruff | sir-qa |
| Migration Alembic | upgrade + downgrade, FK nommées, une seule tête ; sauvegarde de la base avant `upgrade` | sir-backend, sir-orchestrateur |
| Frontend | `ng build` ; `verifier-icones` ; capture du build (1440 px et 390 px) | sir-qa, sir-design |
| Contrat | champs Pydantic = interfaces TS ; `require_permission` = `data.roles` des routes | sir-integration |
| Données | simulation sur données réelles, rapport relu, sauvegarde, exécution, contrôle de cohérence, annulation possible | sir-migration |
| Sécurité | aucun point Critique | sir-securite |
| Déploiement | commandes sans `...` ni `<...>`, une par ligne ; seulement `sirv2-*` ; fichiers d'environnement SENELEC | sir-orchestrateur |

## Leçons intégrées aux portes
Chaque erreur de la section « Erreurs documentées » de `CLAUDE.md` est devenue une vérification :
booléens `IS 1`, COALESCE en GROUP BY (8120), sous-requête dans un agrégat (130), dépassement INT (8115),
durées / END / régions reprises fausses, icônes en texte, `effect()` sans `allowSignalWrites`,
feeders par défaut des postes (23/11/2026).

## Utilisation
- « Où en est-on ? » / « prochaine tâche » → sir-orchestrateur.
- « Contrôle la livraison » → sir-orchestrateur, qui enchaîne sir-qa, sir-integration et, selon le cas, sir-design / sir-securite.
- Une anomalie de données → sir-migration (diagnostic, simulation), jamais d'écriture directe.
