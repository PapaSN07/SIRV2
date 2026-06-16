import { Injectable, NgZone, OnDestroy, signal } from '@angular/core';
import { environment } from '../../../environments/environment';
import { AuthService } from '../auth/auth.service';
import { NotificationEvent, NotificationItem } from '../../shared/models/notification.models';

const MAX_ITEMS = 50;

@Injectable({ providedIn: 'root' })
export class NotificationService implements OnDestroy {
  readonly items = signal<NotificationItem[]>([]);
  readonly connected = signal(false);

  private eventSource: EventSource | null = null;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;

  constructor(
    private readonly auth: AuthService,
    private readonly zone: NgZone,
  ) {}

  connect(): void {
    const token = this.auth.getAccessToken();
    if (!token || this.eventSource) return;

    const url = `${environment.apiUrl}/notifications/stream?token=${encodeURIComponent(token)}`;
    this.eventSource = new EventSource(url);

    this.eventSource.onopen = () => {
      this.zone.run(() => this.connected.set(true));
    };

    this.eventSource.onmessage = (event: MessageEvent<string>) => {
      if (!event.data || event.data.startsWith(':')) return;
      try {
        const payload = JSON.parse(event.data) as NotificationEvent;
        this.zone.run(() => this.pushEvent(payload));
      } catch {
        // ignore malformed payloads
      }
    };

    this.eventSource.onerror = () => {
      this.zone.run(() => this.connected.set(false));
      this.disconnect(false);
      this.scheduleReconnect();
    };
  }

  disconnect(clearItems = true): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
    }
    this.connected.set(false);
    if (clearItems) {
      this.items.set([]);
    }
  }

  unreadCount(): number {
    return this.items().filter((item) => !item.read).length;
  }

  markAllRead(): void {
    this.items.update((list) => list.map((item) => ({ ...item, read: true })));
  }

  ngOnDestroy(): void {
    this.disconnect();
  }

  private pushEvent(event: NotificationEvent): void {
    const item: NotificationItem = {
      ...event,
      id: `${event.event_type}-${event.entity_id}-${Date.now()}`,
      read: false,
    };
    this.items.update((list) => [item, ...list].slice(0, MAX_ITEMS));
  }

  private scheduleReconnect(): void {
    if (this.reconnectTimer || !this.auth.isAuthenticated()) return;
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.connect();
    }, 5000);
  }
}
