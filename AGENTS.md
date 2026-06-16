# Agents SIR — SIRV2

> Branche de développement : `SIR_MSENE`  
> Sprint courant : voir [docs/TODO.md](docs/TODO.md)  
> Backlog global : voir [docs/BACKLOG.md](docs/BACKLOG.md)

## Point d'entrée

En début de session, invoquer **sir-orchestrateur** :

```
Utilise le skill sir-orchestrateur — quelle est la prochaine tâche ?
```

## Les 5 agents

| Agent | Skill | Rôle |
| --- | --- | --- |
| **Orchestrateur** | [sir-orchestrateur](.cursor/skills/sir-orchestrateur/SKILL.md) | Pilotage, ordre des tâches, briefings |
| **Backend** | [sir-backend](.cursor/skills/sir-backend/SKILL.md) | FastAPI, modèles, migrations, services |
| **Frontend** | [sir-frontend](.cursor/skills/sir-frontend/SKILL.md) | Angular, Material, NgRx, guards |
| **Integration** | [sir-integration](.cursor/skills/sir-integration/SKILL.md) | Cohérence backend ↔ frontend |
| **QA** | [sir-qa](.cursor/skills/sir-qa/SKILL.md) | Tests pytest, definition of done TODO |

## Workflow standard

```
sir-orchestrateur → sir-backend → sir-qa → sir-frontend → sir-qa → sir-integration
```

## Sprint 1 (docs/TODO.md)

Ordre : **1.2 DB** → **1.3 Auth** → **1.4 RBAC** → auth UI frontend (après QA 1.3)

## Rules Cursor

| Rule | Fichiers |
| --- | --- |
| `sir-backend.mdc` | `sir-backend/**/*` |
| `sir-frontend.mdc` | `sir-frontend/**/*` |
| `sir-integration.mdc` | backend + frontend |
| `sir-orchestrateur.mdc` | `docs/`, Makefile, docker-compose |
| `sir-qa.mdc` | `sir-backend/tests/**/*` |
