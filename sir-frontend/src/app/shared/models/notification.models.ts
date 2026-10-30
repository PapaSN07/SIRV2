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
  fonction: string | null;
  matricule: number | null;
  /** Une personne peut appartenir à plusieurs groupes (comme dans SIR v1). */
  groupes: GroupeRef[];
}

export interface GroupeRef {
  id: number;
  libelle: string;
}

export type Exploitation = 'BCC' | 'BRC' | 'DISPATCHING';

/** Groupe d'envoi SMS (Répertoire SIR v1), avec le nombre de destinataires joignables. */
export interface GroupeEnvoi {
  id: number;
  libelle: string;
  exploitation: Exploitation | null;
  is_active: boolean;
  nb_destinataires: number;
}

export interface GroupeEnvoiCreate {
  libelle: string;
  exploitation?: Exploitation | null;
}

export interface GroupeEnvoiUpdate {
  libelle?: string;
  exploitation?: Exploitation | null;
  is_active?: boolean;
}

export interface DestinataireCreate {
  nom: string;
  telephone?: string | null;
  email?: string | null;
  utilisateur_id?: number | null;
  service_id?: number | null;
  fonction?: string | null;
  matricule?: number | null;
  groupe_ids?: number[];
}

export interface DestinataireUpdate {
  nom?: string;
  telephone?: string | null;
  email?: string | null;
  utilisateur_id?: number | null;
  service_id?: number | null;
  is_active?: boolean;
  fonction?: string | null;
  matricule?: number | null;
  groupe_ids?: number[];
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
  /** Code renvoyé par Orange SMS Pro (200 = envoyé) et identifiant du message. */
  code_retour?: string | null;
  message_id?: string | null;
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
