export interface RoleAssignment {
  role_id: number;
  scope_service_id?: number | null;
}

export interface RoleInfo {
  role_id: number;
  role_nom: string;
  scope_service_id: number | null;
}

export interface UtilisateurAdmin {
  id: number;
  login: string;
  nom: string;
  prenom: string;
  email: string | null;
  telephone: string | null;
  is_active: boolean;
  premiere_connexion: boolean;
  roles: RoleInfo[];
}

export interface UtilisateurCreate {
  login: string;
  password: string;
  nom: string;
  prenom: string;
  email?: string | null;
  telephone?: string | null;
  roles: RoleAssignment[];
}

export interface UtilisateurUpdate {
  nom?: string;
  prenom?: string;
  email?: string | null;
  telephone?: string | null;
  roles?: RoleAssignment[];
}

export interface ResetPasswordRequest {
  new_password: string;
}

export interface PermissionInfo {
  id: number;
  ressource: string;
  action: string;
  description: string | null;
}

export interface RoleDetail {
  id: number;
  nom: string;
  description: string | null;
  permissions: PermissionInfo[];
}

export interface AuditLogEntry {
  id: number;
  table_name: string;
  record_id: number;
  action: string;
  user_id: number;
  user_login: string | null;
  old_values: string | null;
  new_values: string | null;
  created_at: string;
}

export interface AppSettings {
  sms_gateway_url: string | null;
  smtp_host: string | null;
  smtp_port: number;
  smtp_user: string | null;
  seuil_fugitif_minutes: number;
  environment: string;
}

export interface AppSettingsUpdate {
  seuil_fugitif_minutes?: number;
}

/** IDs alignés sur seed RBAC (ordre d'insertion). */
export const SEED_ROLE_OPTIONS = [
  { id: 1, nom: 'BCC' },
  { id: 2, nom: 'BRC' },
  { id: 3, nom: 'DISPATCHER' },
  { id: 4, nom: 'ADMIN_SCR' },
  { id: 5, nom: 'ADMIN_DISPATCHING' },
  { id: 6, nom: 'ADMIN_SAQS' },
  { id: 7, nom: 'SUPERVISEUR' },
] as const;
