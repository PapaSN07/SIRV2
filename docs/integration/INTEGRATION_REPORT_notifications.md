# Rapport d'intégration — Notifications (Vague 6 + Phase 7 SMS)

**Date :** Juin 2026  
**Statut :** ✅ SSE + changement mot de passe + module SMS UI

## Authentification — première connexion

| Endpoint | Frontend | Statut |
|----------|----------|--------|
| `POST /auth/login` → 403 `FORCE_PASSWORD_CHANGE` | Redirect `/changer-mot-de-passe?login=` | ✅ |
| `POST /auth/change-password` | `AuthService.changePassword()` | ✅ |
| Guard `premiereConnexionGuard` | Routes principales sous `MainLayout` | ✅ |

## SSE notifications

| Endpoint | Frontend | Statut |
|----------|----------|--------|
| `GET /notifications/stream?token=` | `NotificationService` (EventSource) | ✅ |

- Badge + panneau dropdown dans `MainLayoutComponent`
- **Toasts dashboard** : `DashboardComponent` affiche les événements `interruption_creee` et `rapport_pret` | ✅ Phase 8

## Module SMS (Phase 7)

| Endpoint | Frontend | Statut |
|----------|----------|--------|
| `GET /notifications/sms` | `NotificationSmsService.list()` — page `/notifications/sms` | ✅ |
| `GET /notifications/sms/{id}` | Détail panel liste SMS | ✅ |
| `POST /notifications/sms/send` | `SmsSendComponent` — multi-select destinataires + utilisateurs | ✅ |
| `GET/POST/PATCH/DELETE /notifications/destinataires` | `DestinatairesListComponent` CRUD | ✅ |
| `GET /notifications/emails` | `EmailsListComponent` — lecture seule | ✅ |

### Navigation

- Sidebar « Notifications » (rôles ADMIN_SCR, ADMIN_DISPATCHING, ADMIN_SAQS, DISPATCHER)
- Onglets `sir-notifications-nav` : SMS | Envoyer | Destinataires | Emails

### Tests backend

- `tests/integration/test_notifications_sms.py`
- `tests/unit/test_manual_sms_service.py`

## Points d'attention

- Envoi SMS manuel requiert worker Celery actif
- Mode mock SMS si `SMS_GATEWAY_URL` vide
- Utilisateurs sans téléphone exclus de la sélection (badge « sans n° »)
