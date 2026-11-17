import {
  AfterViewInit,
  Component,
  ElementRef,
  EventEmitter,
  Input,
  OnChanges,
  OnDestroy,
  Output,
  ViewChild,
} from '@angular/core';
import * as L from 'leaflet';
import { PosteOuvertCarte } from '../../models/indicateurs.models';

const SENEGAL: L.LatLngBoundsExpression = [
  [12.2, -17.6],
  [16.75, -11.3],
];

/**
 * Carte zoomable (Leaflet, fond OpenStreetMap) des postes impactés.
 * Rouge : poste encore sans date de remise ; violet : poste remis sous tension.
 * Molette / boutons + − pour zoomer, glisser pour se déplacer, clic sur un point pour le détail.
 */
@Component({
  selector: 'sir-carte-postes',
  standalone: true,
  template: `
    <div class="carte" [style.height]="hauteur">
      <div #conteneur class="carte__leaflet" role="application" aria-label="Carte des postes impactés"></div>
      @if (nbSansCoordonnees > 0) {
        <p class="carte__note">
          {{ nbSansCoordonnees }} poste{{ nbSansCoordonnees > 1 ? 's' : '' }} sans coordonnée SIG fiable (non placé{{
            nbSansCoordonnees > 1 ? 's' : ''
          }}).
        </p>
      }
    </div>
  `,
  styles: [
    `
      :host { display: block; }
      .carte { position: relative; border-radius: 12px; overflow: hidden; border: 1px solid #ede9f5; background: #eef3f7; }
      .carte__leaflet { position: absolute; inset: 0; }
      .carte__note {
        position: absolute; left: 54px; top: 10px; z-index: 500; margin: 0; padding: 4px 10px;
        border-radius: 999px; background: rgba(255, 255, 255, 0.92); color: #403a52; font-size: 12px;
        box-shadow: 0 1px 2px rgba(26, 22, 38, 0.12);
      }
      :host ::ng-deep .leaflet-popup-content { margin: 10px 12px; font: 13px/1.45 Inter, sans-serif; color: #1a1626; }
      :host ::ng-deep .leaflet-popup-content strong { color: #262051; }
      :host ::ng-deep .leaflet-popup-content a { color: #5b2a9e; font-weight: 600; }
      :host ::ng-deep .carte-legende {
        padding: 6px 10px; border-radius: 8px; background: rgba(255, 255, 255, 0.94); font: 12px Inter, sans-serif;
        color: #403a52; box-shadow: 0 1px 2px rgba(26, 22, 38, 0.12);
      }
      :host ::ng-deep .carte-legende span { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin: 0 4px 0 8px; vertical-align: -1px; }
      :host ::ng-deep .carte-legende span:first-child { margin-left: 0; }
    `,
  ],
})
export class CartePostesComponent implements AfterViewInit, OnChanges, OnDestroy {
  @Input() points: PosteOuvertCarte[] = [];
  @Input() hauteur = '460px';
  /** Clic sur « Voir l'interruption » dans la bulle d'un poste */
  @Output() ouvrirInterruption = new EventEmitter<number>();

  @ViewChild('conteneur', { static: true }) private conteneur!: ElementRef<HTMLDivElement>;

  nbSansCoordonnees = 0;
  private carte: L.Map | null = null;
  private couche: L.LayerGroup | null = null;
  private observateur: ResizeObserver | null = null;

  ngAfterViewInit(): void {
    this.carte = L.map(this.conteneur.nativeElement, {
      zoomControl: true,
      scrollWheelZoom: true,
      minZoom: 6,
      maxZoom: 18,
      attributionControl: true,
    }).fitBounds(SENEGAL);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '© OpenStreetMap',
    }).addTo(this.carte);
    L.control.scale({ imperial: false }).addTo(this.carte);
    const legende = new L.Control({ position: 'topright' });
    legende.onAdd = () => {
      const div = L.DomUtil.create('div', 'carte-legende');
      div.innerHTML = '<span style="background:#e5484d"></span>Sans remise<span style="background:#5b2a9e"></span>Remis';
      return div;
    };
    legende.addTo(this.carte);
    this.couche = L.layerGroup().addTo(this.carte);
    this.conteneur.nativeElement.addEventListener('click', (event) => {
      const lien = (event.target as HTMLElement).closest('[data-interruption]');
      if (lien) {
        event.preventDefault();
        this.ouvrirInterruption.emit(Number(lien.getAttribute('data-interruption')));
      }
    });
    // Le conteneur peut changer de taille (onglet affiché, menu replié) : Leaflet doit recalculer
    this.observateur = new ResizeObserver(() => this.carte?.invalidateSize());
    this.observateur.observe(this.conteneur.nativeElement);
    this.dessiner(true);
  }

  ngOnChanges(): void {
    this.dessiner(true);
  }

  ngOnDestroy(): void {
    this.observateur?.disconnect();
    this.carte?.remove();
    this.carte = null;
  }

  private dessiner(recadrer: boolean): void {
    if (!this.carte || !this.couche) return;
    this.couche.clearLayers();
    const places = this.points.filter((p) => p.latitude !== null && p.longitude !== null);
    this.nbSansCoordonnees = this.points.length - places.length;
    // Les postes sans remise sont dessinés en dernier, donc au-dessus
    const ordonnes = [...places].sort((a, b) => Number(a.sans_remise) - Number(b.sans_remise));
    for (const p of ordonnes) {
      const couleur = p.sans_remise ? '#e5484d' : '#5b2a9e';
      L.circleMarker([p.latitude!, p.longitude!], {
        radius: p.sans_remise ? 7 : 5,
        color: '#ffffff',
        weight: 1.5,
        fillColor: couleur,
        fillOpacity: 0.9,
      })
        .bindTooltip(this.echapper(p.libelle), { direction: 'top', offset: [0, -6] })
        .bindPopup(this.bulle(p))
        .addTo(this.couche);
    }
    if (recadrer && places.length > 0) {
      const limites = L.latLngBounds(places.map((p) => [p.latitude!, p.longitude!] as L.LatLngTuple));
      this.carte.fitBounds(limites.pad(0.15), { maxZoom: 13 });
    } else if (recadrer) {
      this.carte.fitBounds(SENEGAL);
    }
  }

  private bulle(p: PosteOuvertCarte): string {
    const date = new Date(p.date_apparition).toLocaleString('fr-FR', { dateStyle: 'short', timeStyle: 'short' });
    const lignes = [
      `<strong>${this.echapper(p.libelle)}</strong> <span style="color:#8b85a0">(${this.echapper(p.code)})</span>`,
      p.feeder_libelle ? `Feeder : ${this.echapper(p.feeder_libelle)}` : '',
      p.service_libelle ? `Service : ${this.echapper(p.service_libelle)}` : '',
      `Interruption n° ${p.numero_interruption} — depuis le ${date}`,
      p.sans_remise
        ? '<span style="color:#e5484d;font-weight:600">Pas encore de date de remise</span>'
        : '<span style="color:#1e9e6a;font-weight:600">Remis sous tension</span>',
      `<a href="#" data-interruption="${p.interruption_id}">Voir l'interruption →</a>`,
    ];
    return lignes.filter(Boolean).join('<br>');
  }

  private echapper(texte: string): string {
    return texte.replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]!);
  }
}
