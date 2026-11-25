import {
  AfterViewInit,
  Component,
  ElementRef,
  OnDestroy,
  ViewChild,
  effect,
  input,
  output,
  signal,
} from '@angular/core';
import * as L from 'leaflet';
import { PointCarte } from '../../../shared/models/suivi-incidents.models';
import { COULEUR_NATURE } from '../../../shared/ui/graphique/couleurs-metier';
import { formatDuree, formatEntier } from '../../../shared/utils/formats-indicateurs';

const SENEGAL: L.LatLngBoundsExpression = [
  [12.2, -17.6],
  [16.75, -11.3],
];

const LIBELLE_NATURE: Record<string, string> = {
  incident: 'Incidents',
  delestage: 'Délestages',
  travaux: 'Travaux',
  autre: 'Autres coupures',
};

/**
 * Carte Leaflet des postes touchés : bulle proportionnelle au nombre d'interruptions,
 * couleur de la nature dominante. Recadrée seulement quand l'ensemble des postes change
 * (pas à chaque redessin). Un bouton dans la bulle d'un poste demande un filtre.
 */
@Component({
  selector: 'sir-carte-incidents',
  standalone: true,
  template: `
    <div class="carte-cadre">
      <div #conteneur class="carte" role="region" [attr.aria-label]="titre()"></div>
      @if (fondIndisponible()) {
        <p class="carte-alerte" role="status">Fond de carte indisponible : les positions des postes restent exactes.</p>
      }
      @if (!actif()) {
        <p class="carte-consigne" aria-hidden="true">Cliquez sur la carte pour zoomer ou la déplacer</p>
      }
    </div>
    <!-- Légende hors de la carte sur mobile : elle ne recouvre pas les bulles -->
    <p class="legende-mobile">
      @for (n of natures; track n.cle) {
        <span><i [style.background]="n.couleur"></i>{{ n.libelle }}</span>
      }
      <span class="legende-mobile__taille">Taille : nombre d’interruptions</span>
    </p>
  `,
  styles: [
    `
      :host { display: block; }
      .carte-cadre { position: relative; }
      .carte {
        height: clamp(360px, calc(100vh - 480px), 520px);
        border-radius: 12px; overflow: hidden; border: 1px solid #ede9f5; background: #eef3f7;
      }
      .carte-alerte, .carte-consigne {
        position: absolute; left: 50%; z-index: 800; margin: 0; padding: 4px 12px; transform: translateX(-50%);
        border-radius: 999px; background: rgba(255, 255, 255, 0.95); color: #403a52;
        font: 12px Inter, sans-serif; box-shadow: 0 1px 2px rgba(26, 22, 38, 0.15); white-space: nowrap;
        pointer-events: none;
      }
      .carte-alerte { top: 10px; color: #b42318; }
      .carte-consigne { bottom: 28px; }
      .legende-mobile { display: none; flex-wrap: wrap; gap: 4px 12px; margin: 8px 0 0; color: #403a52; font: 12px Inter, sans-serif; }
      .legende-mobile i { display: inline-block; width: 10px; height: 10px; margin-right: 6px; border-radius: 50%; vertical-align: -1px; }
      .legende-mobile__taille { color: #6b6580; }
      @media (max-width: 767.98px) {
        .legende-mobile { display: flex; }
        :host ::ng-deep .carte-legende { display: none; }
      }
      :host ::ng-deep .leaflet-bar a:focus-visible,
      :host ::ng-deep .leaflet-popup-close-button:focus-visible {
        outline: none; box-shadow: 0 0 0 2px #fff, 0 0 0 4px #5b2a9e;
      }
      @media (pointer: coarse) {
        :host ::ng-deep .leaflet-bar a { width: 44px; height: 44px; line-height: 44px; font-size: 20px; }
        :host ::ng-deep .leaflet-popup-close-button { width: 44px !important; height: 44px !important; font-size: 24px !important; line-height: 44px !important; }
        :host ::ng-deep .carte-filtre { min-height: 44px; }
      }
      :host ::ng-deep .leaflet-popup-content { margin: 10px 12px; font: 13px/1.45 Inter, sans-serif; color: #1a1626; }
      :host ::ng-deep .leaflet-popup-content strong { color: #262051; }
      :host ::ng-deep .carte-filtre {
        margin-top: 6px; padding: 4px 10px; border: 1px solid #5b2a9e; border-radius: 999px;
        background: #fff; color: #5b2a9e; font: 600 12px Inter, sans-serif; cursor: pointer;
      }
      :host ::ng-deep .carte-filtre:focus-visible { outline: 2px solid #5b2a9e; outline-offset: 2px; }
      :host ::ng-deep .carte-legende {
        padding: 6px 10px; border-radius: 8px; background: rgba(255, 255, 255, 0.95); font: 12px Inter, sans-serif;
        color: #403a52; box-shadow: 0 1px 2px rgba(26, 22, 38, 0.12); line-height: 1.6;
      }
      :host ::ng-deep .carte-legende i {
        display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 6px; vertical-align: -1px;
        border: 1px solid #fff;
      }
    `,
  ],
})
export class CarteIncidentsComponent implements AfterViewInit, OnDestroy {
  readonly points = input.required<PointCarte[]>();
  readonly titre = input('Carte des postes touchés');
  /** Molette et glisser actifs seulement après un clic sur la carte (la page défile sinon). */
  readonly actif = signal(false);
  readonly fondIndisponible = signal(false);
  readonly natures = Object.entries(LIBELLE_NATURE).map(([cle, libelle]) => ({ cle, libelle, couleur: COULEUR_NATURE[cle] }));
  /** Demande de filtre depuis la bulle d'un poste : son feeder… (le parent décide). */
  readonly filtrerPoste = output<PointCarte>();

  @ViewChild('conteneur', { static: true }) private conteneur!: ElementRef<HTMLDivElement>;

  private carte: L.Map | null = null;
  private couche: L.LayerGroup | null = null;
  private observateur: ResizeObserver | null = null;
  private empreinte = '';
  private parId = new Map<number, PointCarte>();

  constructor() {
    effect(() => this.dessiner(this.points()));
  }

  ngAfterViewInit(): void {
    // Canvas : jusqu'à 3 000 bulles sans ralentir le zoom (SVG = un nœud DOM par bulle)
    this.carte = L.map(this.conteneur.nativeElement, {
      minZoom: 6,
      maxZoom: 18,
      // Canvas : jusqu'à 3 000 bulles sans ralentir le zoom, et aucune bulle dans l'ordre de tabulation
      preferCanvas: true,
      zoomControl: false,
      // La molette et le glisser d'un doigt font défiler la page tant que la carte n'est pas activée
      scrollWheelZoom: false,
      dragging: !L.Browser.mobile,
    }).fitBounds(SENEGAL);
    L.control.zoom({ zoomInTitle: 'Zoomer', zoomOutTitle: 'Dézoomer' }).addTo(this.carte);
    this.carte.attributionControl.setPrefix('<a href="https://leafletjs.com">Leaflet</a>');
    const tuiles = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '© OpenStreetMap',
    }).addTo(this.carte);
    tuiles.on('tileerror', () => this.fondIndisponible.set(true));
    tuiles.on('tileload', () => this.fondIndisponible.set(false));
    const activer = () => {
      if (this.actif() || !this.carte) return;
      this.actif.set(true);
      this.carte.scrollWheelZoom.enable();
      this.carte.dragging.enable();
    };
    this.carte.on('click focus', activer);
    this.carte.on('mouseout', () => {
      if (!this.carte || L.Browser.mobile) return;
      this.actif.set(false);
      this.carte.scrollWheelZoom.disable();
    });
    this.carte.on('popupopen', (e: L.PopupEvent) => {
      e.popup.getElement()?.querySelector('.leaflet-popup-close-button')?.setAttribute('aria-label', 'Fermer');
    });
    L.control.scale({ imperial: false }).addTo(this.carte);
    const legende = new L.Control({ position: 'topright' });
    legende.onAdd = () => {
      const div = L.DomUtil.create('div', 'carte-legende');
      div.innerHTML =
        Object.entries(LIBELLE_NATURE)
          .map(([cle, libelle]) => `<i style="background:${COULEUR_NATURE[cle]}"></i>${libelle}`)
          .join('<br>') + '<br><span style="color:#6b6580">Taille : nombre d’interruptions</span>';
      return div;
    };
    legende.addTo(this.carte);
    this.couche = L.layerGroup().addTo(this.carte);
    this.conteneur.nativeElement.addEventListener('click', (evenement) => {
      const bouton = (evenement.target as HTMLElement).closest<HTMLElement>('[data-poste]');
      const point = bouton ? this.parId.get(Number(bouton.dataset['poste'])) : undefined;
      if (point) this.filtrerPoste.emit(point);
    });
    this.observateur = new ResizeObserver(() => this.carte?.invalidateSize());
    this.observateur.observe(this.conteneur.nativeElement);
    this.dessiner(this.points());
  }

  ngOnDestroy(): void {
    this.observateur?.disconnect();
    this.carte?.remove();
    this.carte = null;
  }

  private dessiner(points: PointCarte[]): void {
    if (!this.carte || !this.couche) return;
    this.couche.clearLayers();
    this.parId = new Map(points.map((p) => [p.poste_id, p]));
    const max = Math.max(1, ...points.map((p) => p.nombre));
    // Les plus petites bulles au-dessus des grandes, pour rester cliquables
    for (const p of [...points].sort((a, b) => b.nombre - a.nombre)) {
      L.circleMarker([p.latitude, p.longitude], {
        radius: 4 + 14 * Math.sqrt(p.nombre / max),
        color: '#ffffff',
        weight: 1.5,
        fillColor: COULEUR_NATURE[p.nature_dominante] ?? '#6b6580',
        fillOpacity: 0.85,
      })
        .bindTooltip(this.echapper(p.libelle), { direction: 'top', offset: [0, -6] })
        .bindPopup(() => this.bulle(p))
        .addTo(this.couche);
    }
    // Recadrage seulement si l'ensemble des postes a changé (pas au simple redessin)
    const empreinte = points.map((p) => p.poste_id).join(',');
    if (empreinte !== this.empreinte) {
      this.empreinte = empreinte;
      if (points.length) {
        const limites = L.latLngBounds(points.map((p) => [p.latitude, p.longitude] as L.LatLngTuple));
        this.carte.fitBounds(limites.pad(0.15), { maxZoom: 13 });
      } else {
        this.carte.fitBounds(SENEGAL);
      }
    }
  }

  private bulle(p: PointCarte): string {
    return [
      `<strong>${this.echapper(p.libelle)}</strong> <span style="color:#6b6580">(${this.echapper(p.code)})</span>`,
      p.feeder ? `Feeder : ${this.echapper(p.feeder)}` : '',
      `${formatEntier(p.nombre)} interruption${p.nombre > 1 ? 's' : ''} · ${formatDuree(p.duree_heures)} cumulées`,
      `${formatEntier(p.clients)} clients coupés (cumul)`,
      `Nature dominante : ${LIBELLE_NATURE[p.nature_dominante] ?? p.nature_dominante}`,
      `<span style="color:#6b6580">Placé par ${p.localisation === 'rapprochement' ? 'le rapprochement SIG' : 'le nom du poste'}</span>`,
      p.feeder ? `<button type="button" class="carte-filtre" data-poste="${p.poste_id}">Filtrer sur ce feeder</button>` : '',
    ]
      .filter(Boolean)
      .join('<br>');
  }

  private echapper(texte: string): string {
    return texte.replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]!);
  }
}
