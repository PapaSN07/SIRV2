# Rapport d'intégration — Interruptions Distribution (Sprint 3 · F3)

**Date :** Juin 2026  
**Statut :** ✅ Aligné backend · Module Angular F3 implémenté (liste, formulaire, détail, édition)

## Contrats API vérifiés

| Endpoint | Backend (Pydantic) | Frontend TS | Statut |
|----------|-------------------|-------------|--------|
| `GET /interruptions/distribution` | `PaginatedResponse[InterruptionDistributionResponse]` | `InterruptionListParams` + snake_case | ✅ |
| `GET /interruptions/distribution/{id}` | `InterruptionDistributionDetailResponse` | `InterruptionDistributionDetail` | ✅ |
| `POST /interruptions/distribution` | `InterruptionDistributionCreate` | `InterruptionDistributionCreate` | ✅ |
| `PUT /interruptions/distribution/{id}` | `InterruptionDistributionUpdate` | `InterruptionDistributionUpdate` | ✅ |
| `PATCH …/{id}/cloturer` | `InterruptionClotureRequest` | `InterruptionClotureRequest` | ✅ |
| `PATCH …/{id}/valider` | — (body vide) | `{}` | ✅ |
| `GET/POST/DELETE …/{id}/postes` | `PosteImpacteResponse` / `PosteInterruptionCreate` | aligné | ✅ |
| Enveloppe | `ApiResponse[T]` | `ApiResponse<T>` | ✅ |
| Pagination | `page`, `page_size` | `page`, `page_size` | ✅ |

## RBAC frontend

| Action | Rôles UI (`RoleGuard` / `*sirHasRole`) | Backend |
|--------|----------------------------------------|---------|
| Liste / détail | BCC, BRC, ADMIN_SCR, ADMIN_SAQS, SUPERVISEUR | `read` permission |
| Création | BCC, ADMIN_SCR | `create` permission |
| Modification | BCC, ADMIN_SCR (statut `en_cours` uniquement) | `update` permission |
| Clôture | BCC, ADMIN_SCR (bouton) | `update` permission |
| Validation | SUPERVISEUR, ADMIN_SCR, ADMIN_SAQS | `validate` permission |

## Routes Angular (lazy)

- `/interruptions/distribution` — liste + filtres
- `/interruptions/distribution/nouveau` — création
- `/interruptions/distribution/:id/modifier` — édition (en cours)
- `/interruptions/distribution/:id` — détail, postes, clôture, validation

## UI refonte (Vague 1)

| Écran | Composants partagés | Maquette |
|-------|---------------------|----------|
| Liste | `sir-page-header`, `sir-status-chip`, `sir-paginator` | `liste_des_interruptions_sir_senelec` |
| Formulaire | `sir-page-header`, Reactive Forms, `.sir-btn` | `saisie_interruption_distribution_sir_senelec` |
| Détail | `sir-page-header`, `sir-status-chip`, timeline workflow | `details_de_l_interruption_sir_distribution_senelec` |

## Points d'attention

- Dates : `datetime-local` → ISO 8601 avant envoi API
- Champs API en **snake_case** côté TS (cohérent avec référentiel existant)
- Masquage UI ≠ sécurité — le backend reste source de vérité RBAC
- Comptes dev seed : `bcc.dev` / `superviseur.dev` (mdp `DevSir123!`)

## Tests manuels recommandés

1. Login `bcc.dev` → créer interruption → ajouter poste → clôturer
2. Login `bcc.dev` → modifier interruption en cours → vérifier redirection détail
3. Login `superviseur.dev` → valider interruption clôturée
4. Login BCC → bouton « Valider » absent sur interruption clôturée ; bouton « Modifier » absent si statut ≠ en cours
