import { Routes } from '@angular/router';
import { authGuard, premiereConnexionGuard, roleGuard } from './core/auth/role.guard';

const DISTRIBUTION_READ_ROLES = ['BCC', 'BRC', 'ADMIN_SCR', 'ADMIN_SAQS', 'SUPERVISEUR'];
const DISTRIBUTION_WRITE_ROLES = ['BCC', 'BRC', 'ADMIN_SCR'];
const VALIDATION_ROLES = ['SUPERVISEUR', 'ADMIN_SCR', 'ADMIN_SAQS'];
const TRANSPORT_READ_ROLES = ['DISPATCHER', 'ADMIN_DISPATCHING', 'ADMIN_SAQS'];
const TRANSPORT_WRITE_ROLES = ['DISPATCHER', 'ADMIN_DISPATCHING'];
const INDICATEURS_ROLES = ['BCC', 'BRC', 'ADMIN_SCR', 'ADMIN_SAQS', 'SUPERVISEUR'];
const RAPPORTS_ROLES = ['BCC', 'BRC', 'DISPATCHER', 'ADMIN_SCR', 'ADMIN_DISPATCHING', 'ADMIN_SAQS', 'SUPERVISEUR'];
const ADMIN_REF_ROLES = ['ADMIN_SCR', 'ADMIN_DISPATCHING', 'BCC', 'BRC', 'DISPATCHER', 'ADMIN_SAQS', 'SUPERVISEUR'];
const ADMIN_RESEAU_DIST_ROLES = ['ADMIN_SCR', 'BCC', 'BRC', 'ADMIN_SAQS', 'SUPERVISEUR'];
const ADMIN_RESEAU_TRANS_ROLES = ['ADMIN_DISPATCHING', 'DISPATCHER', 'ADMIN_SAQS'];
const ADMIN_USERS_ROLES = ['ADMIN_SCR', 'ADMIN_DISPATCHING'];
const NOTIFICATIONS_READ_ROLES = ['ADMIN_SCR', 'ADMIN_DISPATCHING', 'ADMIN_SAQS', 'DISPATCHER'];
const NOTIFICATIONS_ADMIN_ROLES = ['ADMIN_SCR', 'ADMIN_DISPATCHING', 'ADMIN_SAQS'];

export const routes: Routes = [
  {
    path: 'login',
    loadComponent: () =>
      import('./features/auth/login/login.component').then((m) => m.LoginComponent),
  },
  {
    path: 'changer-mot-de-passe',
    loadComponent: () =>
      import('./features/auth/change-password/change-password.component').then(
        (m) => m.ChangePasswordComponent,
      ),
  },
  {
    path: '',
    canActivate: [authGuard, premiereConnexionGuard],
    loadComponent: () =>
      import('./shared/layout/main-layout/main-layout.component').then((m) => m.MainLayoutComponent),
    children: [
      {
        path: '',
        loadComponent: () =>
          import('./features/dashboard/dashboard.component').then((m) => m.DashboardComponent),
      },
      {
        path: 'acces-refuse',
        loadComponent: () =>
          import('./features/auth/access-denied/access-denied.component').then(
            (m) => m.AccessDeniedComponent,
          ),
      },
      {
        path: 'interruptions/distribution',
        canActivate: [roleGuard],
        data: { roles: DISTRIBUTION_READ_ROLES },
        loadComponent: () =>
          import('./features/interruptions-distribution/interruption-list/interruption-list.component').then(
            (m) => m.InterruptionListComponent,
          ),
      },
      {
        path: 'interruptions/distribution/nouveau',
        canActivate: [roleGuard],
        data: { roles: DISTRIBUTION_WRITE_ROLES },
        loadComponent: () =>
          import('./features/interruptions-distribution/interruption-form/interruption-form.component').then(
            (m) => m.InterruptionFormComponent,
          ),
      },
      {
        path: 'interruptions/distribution/:id/modifier',
        canActivate: [roleGuard],
        data: { roles: DISTRIBUTION_WRITE_ROLES },
        loadComponent: () =>
          import('./features/interruptions-distribution/interruption-form/interruption-form.component').then(
            (m) => m.InterruptionFormComponent,
          ),
      },
      {
        path: 'interruptions/distribution/:id',
        canActivate: [roleGuard],
        data: { roles: DISTRIBUTION_READ_ROLES },
        loadComponent: () =>
          import('./features/interruptions-distribution/interruption-detail/interruption-detail.component').then(
            (m) => m.InterruptionDetailComponent,
          ),
      },
      {
        path: 'interruptions/transport',
        canActivate: [roleGuard],
        data: { roles: TRANSPORT_READ_ROLES },
        loadComponent: () =>
          import('./features/interruptions-transport/interruption-list/interruption-list.component').then(
            (m) => m.InterruptionTransportListComponent,
          ),
      },
      {
        path: 'interruptions/transport/nouveau',
        canActivate: [roleGuard],
        data: { roles: TRANSPORT_WRITE_ROLES },
        loadComponent: () =>
          import('./features/interruptions-transport/interruption-form/interruption-form.component').then(
            (m) => m.InterruptionTransportFormComponent,
          ),
      },
      {
        path: 'interruptions/transport/:id/modifier',
        canActivate: [roleGuard],
        data: { roles: TRANSPORT_WRITE_ROLES },
        loadComponent: () =>
          import('./features/interruptions-transport/interruption-form/interruption-form.component').then(
            (m) => m.InterruptionTransportFormComponent,
          ),
      },
      {
        path: 'interruptions/transport/:id',
        canActivate: [roleGuard],
        data: { roles: TRANSPORT_READ_ROLES },
        loadComponent: () =>
          import('./features/interruptions-transport/interruption-detail/interruption-detail.component').then(
            (m) => m.InterruptionTransportDetailComponent,
          ),
      },
      {
        path: 'workflow/validation',
        canActivate: [roleGuard],
        data: { roles: VALIDATION_ROLES },
        loadComponent: () =>
          import('./features/workflow/validation-queue/validation-queue.component').then(
            (m) => m.ValidationQueueComponent,
          ),
      },
      {
        path: 'indicateurs',
        canActivate: [roleGuard],
        data: { roles: INDICATEURS_ROLES },
        loadComponent: () =>
          import('./features/indicateurs/indicateurs-hub/indicateurs-hub.component').then(
            (m) => m.IndicateursHubComponent,
          ),
      },
      {
        path: 'rapports',
        canActivate: [roleGuard],
        data: { roles: RAPPORTS_ROLES },
        loadComponent: () =>
          import('./features/rapports/rapports-hub/rapports-hub.component').then(
            (m) => m.RapportsHubComponent,
          ),
      },
      {
        path: 'referentiel',
        redirectTo: 'admin/referentiel',
        pathMatch: 'full',
      },
      {
        path: 'admin',
        redirectTo: 'admin/referentiel',
        pathMatch: 'full',
      },
      {
        path: 'admin/referentiel',
        canActivate: [roleGuard],
        data: { roles: ADMIN_REF_ROLES },
        loadComponent: () =>
          import('./features/referentiel/referentiel-list/referentiel-list.component').then(
            (m) => m.ReferentielListComponent,
          ),
      },
      {
        path: 'admin/reseau/distribution',
        canActivate: [roleGuard],
        data: { roles: ADMIN_RESEAU_DIST_ROLES },
        loadComponent: () =>
          import('./features/admin/reseau-distribution-admin/reseau-distribution-admin.component').then(
            (m) => m.ReseauDistributionAdminComponent,
          ),
      },
      {
        path: 'admin/reseau/transport',
        canActivate: [roleGuard],
        data: { roles: ADMIN_RESEAU_TRANS_ROLES },
        loadComponent: () =>
          import('./features/admin/reseau-transport-admin/reseau-transport-admin.component').then(
            (m) => m.ReseauTransportAdminComponent,
          ),
      },
      {
        path: 'admin/utilisateurs',
        canActivate: [roleGuard],
        data: { roles: ADMIN_USERS_ROLES },
        loadComponent: () =>
          import('./features/admin/utilisateurs/utilisateurs-list.component').then(
            (m) => m.UtilisateursListComponent,
          ),
      },
      {
        path: 'admin/roles',
        canActivate: [roleGuard],
        data: { roles: ADMIN_USERS_ROLES },
        loadComponent: () =>
          import('./features/admin/roles-list/roles-list.component').then(
            (m) => m.RolesListComponent,
          ),
      },
      {
        path: 'admin/audit-log',
        canActivate: [roleGuard],
        data: { roles: ADMIN_USERS_ROLES },
        loadComponent: () =>
          import('./features/admin/audit-log-list/audit-log-list.component').then(
            (m) => m.AuditLogListComponent,
          ),
      },
      {
        path: 'admin/settings',
        canActivate: [roleGuard],
        data: { roles: ADMIN_USERS_ROLES },
        loadComponent: () =>
          import('./features/admin/settings-page/settings-page.component').then(
            (m) => m.SettingsPageComponent,
          ),
      },
      {
        path: 'napt',
        canActivate: [roleGuard],
        data: { roles: ['BCC', 'ADMIN_SCR', 'ADMIN_SAQS', 'SUPERVISEUR'] },
        loadComponent: () =>
          import('./features/napt/napt-list/napt-list.component').then((m) => m.NaptListComponent),
      },
      {
        path: 'notifications/sms',
        canActivate: [roleGuard],
        data: { roles: NOTIFICATIONS_READ_ROLES },
        loadComponent: () =>
          import('./features/notifications/sms-list/sms-list.component').then(
            (m) => m.SmsListComponent,
          ),
      },
      {
        path: 'notifications/sms/envoyer',
        canActivate: [roleGuard],
        data: { roles: NOTIFICATIONS_ADMIN_ROLES },
        loadComponent: () =>
          import('./features/notifications/sms-send/sms-send.component').then(
            (m) => m.SmsSendComponent,
          ),
      },
      {
        path: 'notifications/destinataires',
        canActivate: [roleGuard],
        data: { roles: NOTIFICATIONS_READ_ROLES },
        loadComponent: () =>
          import('./features/notifications/destinataires-list/destinataires-list.component').then(
            (m) => m.DestinatairesListComponent,
          ),
      },
      {
        path: 'notifications/emails',
        canActivate: [roleGuard],
        data: { roles: NOTIFICATIONS_READ_ROLES },
        loadComponent: () =>
          import('./features/notifications/emails-list/emails-list.component').then(
            (m) => m.EmailsListComponent,
          ),
      },
      {
        path: 'utilisateurs',
        redirectTo: 'admin/utilisateurs',
        pathMatch: 'full',
      },
      {
        path: 'geo',
        loadComponent: () =>
          import('./features/geo/geo-cascade/geo-cascade.component').then(
            (m) => m.GeoCascadeComponent,
          ),
      },
    ],
  },
  { path: '**', redirectTo: '' },
];
