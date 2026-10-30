export type NotificationEventType =
  | 'interruption_creee'
  | 'interruption_cloturee'
  | 'interruption_validee'
  | 'rapport_pret'
  | 'napt_soumis';

export interface NotificationEvent {
  event_type: NotificationEventType | string;
  entity_type: string;
  entity_id: number;
  message: string;
  service_id: number | null;
  created_at: string;
}

export interface NotificationItem extends NotificationEvent {
  id: string;
  read: boolean;
}

export interface Destinataire {
  id: number;
  nom: string;
  telephone: string | null;
  email: string | null;
  utilisateur_id: number | null;
  service_id: number | null;
  is_active: boolean;
  fonction?: string | null;
  groupe_id?: number | null;
  groupe_libelle?: string | null;
}

/** Groupe d'envoi SMS (Répertoire SIR v1), avec le nombre de destinataires joignables. */
export interface GroupeEnvoi {
  id: number;
  libelle: string;
  nb_destinataires: number;
}

export interface DestinataireCreate {
  nom: string;
  telephone?: string | null;
  email?: string | null;
  utilisateur_id?: number | null;
  service_id?: number | null;
}

export interface DestinataireUpdate {
  nom?: string;
  telephone?: string | null;
  email?: string | null;
  utilisateur_id?: number | null;
  service_id?: number | null;
  is_active?: boolean;
}

export interface SmsEnvoye {
  id: number;
  destinataire_id: number;
  entity_type: string | null;
  entity_id: number | null;
  contenu: string;
  statut: string;
  sent_at: string | null;
  erreur: string | null;
  created_at: string;
  destinataire_nom: string | null;
  destinataire_telephone: string | null;
  utilisateur_login: string | null;
}

export interface EmailEnvoye {
  id: number;
  destinataire_id: number;
  entity_type: string | null;
  entity_id: number | null;
  sujet: string;
  corps: string;
  statut: string;
  sent_at: string | null;
  erreur: string | null;
  created_at: string;
}

export interface ManualSmsSendRequest {
  message: string;
  destinataire_ids?: number[];
  utilisateur_ids?: number[];
}

export interface ManualSmsSendResponse {
  sent_count: number;
  sms_ids: number[];
}

export interface NotificationListParams {
  page?: number;
  page_size?: number;
  entity_type?: string;
  statut?: string;
  date_debut?: string;
  date_fin?: string;
}
