export interface LoginRequest {
  login: string;
  password: string;
}

export interface ChangePasswordRequest {
  login: string;
  current_password: string;
  new_password: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

export interface MeResponse {
  id: number;
  login: string;
  nom: string;
  prenom: string;
  role_label: string | null;
  service_id: number | null;
  premiere_connexion: boolean;
  is_active: boolean;
}
