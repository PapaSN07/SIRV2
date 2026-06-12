export type TypeDirection = 'distribution' | 'transport' | 'omvg';
export type StatutInterruption = 'en_cours' | 'cloture' | 'valide' | 'archive';

export interface Interruption {
  id: number;
  numeroInterruption: number;
  typeDirection: TypeDirection;
  statut: StatutInterruption;
  dateApparition: string;
  dateRemise?: string;
  dureeInterruption?: number;
  feederId?: number;
  feederLibelle?: string;
  causeId: number;
  causeLibelle?: string;
  natureId: number;
  siegeId: number;
  signalisationId: number;
  serviceId: number;
  creePar: number;
  creeLe: string;
}

export interface InterruptionCreate {
  typeDirection: TypeDirection;
  dateApparition: string;
  feederId: number;
  causeId: number;
  natureId: number;
  siegeId: number;
  signalisationId: number;
  observations?: string;
}
