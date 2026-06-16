import { StatutInterruption } from '../models/interruption.models';

const STATUT_LABELS: Record<StatutInterruption, string> = {
  en_cours: 'En cours',
  cloture: 'Clôturée',
  valide: 'Validée',
  archive: 'Archivée',
};

export function statutLabel(statut: StatutInterruption): string {
  return STATUT_LABELS[statut];
}

export const STATUTS_INTERRUPTION: StatutInterruption[] = [
  'en_cours',
  'cloture',
  'valide',
  'archive',
];
