export interface RiskFactor {
  code: string;
  label: string;
  weight: number | null;
}

export interface RiskPrediction {
  id: number;
  entity_type: string;
  entity_id: number;
  entity_libelle: string | null;
  horizon_days: number;
  risk_score: number;
  risk_level: string;
  model_version: string;
  factors: RiskFactor[];
  recommendation: string | null;
  service_id: number | null;
  feeder_id: number | null;
  calculated_at: string;
}

export interface RiskListResponse {
  items: RiskPrediction[];
  model_version: string;
  horizon_days: number;
  generated_hint: string;
}

export interface DatamartFeederMoisItem {
  feeder_id: number;
  feeder_code: string | null;
  feeder_libelle: string | null;
  service_id: number | null;
  annee: number;
  mois: number;
  nb_interruptions: number;
  nb_force_majeure: number;
  duree_moyenne_minutes: number | null;
  clients_touches_total: number;
}

export interface DatamartTronconItem {
  troncon_sig_id: number;
  troncon_sig_libelle: string | null;
  feeder_id: number | null;
  service_id: number | null;
  nb_interruptions: number;
  duree_moyenne_minutes: number | null;
  derniere_apparition: string | null;
}

export interface DatamartPosteItem {
  poste_id: number;
  poste_code: string | null;
  poste_libelle: string | null;
  feeder_id: number | null;
  service_id: number | null;
  nb_impactes: number;
  clients_touches_total: number;
  derniere_apparition: string | null;
}

export interface DatamartSummary {
  feeders_mois: DatamartFeederMoisItem[];
  troncons_sig: DatamartTronconItem[];
  postes: DatamartPosteItem[];
}

export interface AssistantChatRequest {
  question: string;
  feeder_id?: number | null;
  interruption_id?: number | null;
}

export interface AssistantChatResponse {
  conversation_id: number;
  answer: string;
  predictions: RiskPrediction[];
  phase: string;
  disclaimer: string;
}

export interface AssistantFeedbackRequest {
  accepted: boolean;
}

export interface ScoringJobResponse {
  status: string;
  feeders_scored: number;
  model_version: string;
  horizon_days: number;
}
