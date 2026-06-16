import { NotificationEventType } from '../../shared/models/notification.models';

const LABELS: Record<string, string> = {
  interruption_creee: 'Nouvelle interruption',
  interruption_cloturee: 'Interruption clôturée',
  interruption_validee: 'Interruption validée',
  rapport_pret: 'Rapport disponible',
  napt_soumis: 'NAPT soumis',
};

export function notificationEventLabel(eventType: NotificationEventType | string): string {
  return LABELS[eventType] ?? 'Notification';
}

export function notificationRelativeTime(isoDate: string): string {
  const date = new Date(isoDate);
  const diffMs = Date.now() - date.getTime();
  const minutes = Math.floor(diffMs / 60000);
  if (minutes < 1) return 'À l\'instant';
  if (minutes < 60) return `Il y a ${minutes} min`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `Il y a ${hours} h`;
  return date.toLocaleDateString('fr-FR');
}
