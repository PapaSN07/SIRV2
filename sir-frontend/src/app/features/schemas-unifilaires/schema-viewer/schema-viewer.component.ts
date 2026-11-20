import {
  AfterViewInit,
  Component,
  ElementRef,
  OnChanges,
  OnDestroy,
  SimpleChanges,
  ViewChild,
  inject,
  input,
  output,
} from '@angular/core';
import * as L from 'leaflet';
import { PosteSchema, SchemaUnifilaire } from '../../../shared/models/schema-unifilaire.models';
import { SchemaUnifilaireService } from '../schema-unifilaire.service';

/** État d'affichage d'un poste du schéma (couleur de sa zone cliquable). */
export type EtatPoste = 'debut' | 'fin' | 'chemin' | 'selection' | 'impacte' | 'non-relie' | 'focus';

const COULEURS: Record<EtatPoste, { couleur: string; fond: number }> = {
  debut: { couleur: '#1f7a4d', fond: 0.35 },
  fin: { couleur: '#c2006a', fond: 0.35 },
  chemin: { couleur: '#5b2a9e', fond: 0.28 },
  selection: { couleur: '#e6007e', fond: 0.28 },
  impacte: { couleur: '#c77700', fond: 0.22 },
  'non-relie': { couleur: '#9a6b00', fond: 0.12 },
  focus: { couleur: '#0b6bcb', fond: 0.3 },
};

/**
 * Visionneuse d'un schéma unifilaire : tuiles du PDF AutoCAD (Leaflet, CRS.Simple), chaque poste est une
 * zone cliquable (symbole + libellé). Molette pour zoomer, glisser pour se déplacer.
 */
@Component({
  selector: 'sir-schema-viewer',
  standalone: true,
  template: `<div #conteneur class="schema" role="application" [attr.aria-label]="'Schéma unifilaire ' + (schema()?.nom ?? '')"></div>`,
  styles: [
    `
      :host { display: block; height: 100%; }
      .schema { width: 100%; height: 100%; background: #fff; }
      :host ::ng-deep .leaflet-container { background: #fff; font: 13px Inter, sans-serif; }
      :host ::ng-deep .schema-infobulle { font: 600 12px Inter, sans-serif; color: #262051; }
    `,
  ],
})
export class SchemaViewerComponent implements AfterViewInit, OnChanges, OnDestroy {
  private readonly service = inject(SchemaUnifilaireService);

  readonly schema = input<SchemaUnifilaire | null>(null);
  readonly postes = input<PosteSchema[]>([]);
  /** Couleur de certains postes (sélection, chemin, déjà impactés…) ; les autres restent transparents. */
  readonly etats = input<ReadonlyMap<number, EtatPoste>>(new Map());
  /** Tracé à surligner (chemin entre deux postes), en points PDF. */
  readonly trace = input<[number, number][]>([]);
  readonly posteClique = output<PosteSchema>();

  @ViewChild('conteneur', { static: true }) private conteneur!: ElementRef<HTMLDivElement>;

  private carte: L.Map | null = null;
  private tuiles: L.GridLayer | null = null;
  private zones = new Map<number, L.Rectangle>();
  private coucheZones: L.LayerGroup | null = null;
  private coucheTrace: L.Polyline | null = null;
  private rendu = L.canvas({ padding: 0.3, tolerance: 2 });
  private facteur = 1;
  private observateur: ResizeObserver | null = null;

  ngAfterViewInit(): void {
    this.carte = L.map(this.conteneur.nativeElement, {
      crs: L.CRS.Simple,
      zoomControl: true,
      attributionControl: false,
      zoomSnap: 0.5,
      wheelPxPerZoomLevel: 90,
      preferCanvas: true,
    });
    this.observateur = new ResizeObserver(() => this.carte?.invalidateSize());
    this.observateur.observe(this.conteneur.nativeElement);
    this.chargerSchema();
    this.dessinerZones();
    this.dessinerTrace();
  }

  ngOnChanges(changes: SimpleChanges): void {
    if (!this.carte) return;
    if (changes['schema']) this.chargerSchema();
    if (changes['schema'] || changes['postes']) this.dessinerZones();
    else if (changes['etats']) this.colorer();
    if (changes['trace'] || changes['schema']) this.dessinerTrace();
  }

  ngOnDestroy(): void {
    this.observateur?.disconnect();
    this.carte?.remove();
    this.carte = null;
  }

  /** Centre la vue sur un poste (recherche par nom). */
  centrerSur(poste: PosteSchema): void {
    if (!this.carte) return;
    this.carte.fitBounds(this.bornes(poste).pad(4), { maxZoom: (this.schema()?.zoom_max ?? 6) + 1 });
  }

  /** Points PDF → coordonnées Leaflet (au zoom maximal, 1 point = 2 pixels). */
  private ll(x: number, y: number): L.LatLng {
    return L.latLng(-y / this.facteur, x / this.facteur);
  }

  private bornes(p: PosteSchema): L.LatLngBounds {
    const b = L.latLngBounds(this.ll(p.x0, p.y0), this.ll(p.x1, p.y1));
    if (p.lx0 !== null && p.ly0 !== null && p.lx1 !== null && p.ly1 !== null) {
      b.extend(this.ll(p.lx0, p.ly0)).extend(this.ll(p.lx1, p.ly1));
    }
    return b;
  }

  private chargerSchema(): void {
    const carte = this.carte;
    const schema = this.schema();
    if (!carte) return;
    if (this.tuiles) {
      carte.removeLayer(this.tuiles);
      this.tuiles = null;
    }
    if (!schema) return;
    this.facteur = 2 ** (schema.zoom_max - 1);
    const limites = L.latLngBounds(this.ll(0, schema.hauteur), this.ll(schema.largeur, 0));
    carte.setMinZoom(0);
    carte.setMaxZoom(schema.zoom_max + 2);
    carte.setMaxBounds(limites.pad(0.15));
    this.tuiles = this.coucheTuiles(schema);
    this.tuiles.addTo(carte);
    carte.fitBounds(limites);
  }

  /** Tuiles chargées par HttpClient (jeton joint), affichées en URL d'objet libérée au déchargement. */
  private coucheTuiles(schema: SchemaUnifilaire): L.GridLayer {
    const service = this.service;
    const Couche = L.GridLayer.extend({
      createTile(coords: L.Coords, fait: L.DoneCallback): HTMLElement {
        const img = document.createElement('img');
        img.alt = '';
        img.setAttribute('role', 'presentation');
        if (coords.x < 0 || coords.y < 0 || coords.z > schema.zoom_max) {
          setTimeout(() => fait(undefined, img));
          return img;
        }
        service.tuile(schema.id, coords.z, coords.x, coords.y).subscribe({
          next: (blob) => {
            if (blob) {
              img.onload = () => fait(undefined, img);
              img.onerror = () => fait(undefined, img);
              img.src = URL.createObjectURL(blob);
            } else {
              fait(undefined, img);
            }
          },
          error: () => fait(undefined, img),
        });
        return img;
      },
    });
    const couche = new (Couche as unknown as new (o: L.GridLayerOptions) => L.GridLayer)({
      tileSize: 256,
      minZoom: 0,
      maxNativeZoom: schema.zoom_max,
      maxZoom: schema.zoom_max + 2,
      noWrap: true,
      bounds: L.latLngBounds(this.ll(0, schema.hauteur), this.ll(schema.largeur, 0)),
    });
    couche.on('tileunload', (e: L.TileEvent) => {
      const src = (e.tile as HTMLImageElement).src;
      if (src?.startsWith('blob:')) URL.revokeObjectURL(src);
    });
    return couche;
  }

  private dessinerZones(): void {
    const carte = this.carte;
    if (!carte) return;
    this.coucheZones?.remove();
    this.zones.clear();
    if (!this.schema()) return;
    const groupe = L.layerGroup();
    for (const p of this.postes()) {
      const zone = L.rectangle(this.bornes(p), {
        renderer: this.rendu,
        weight: 1.5,
        color: 'transparent',
        fillColor: 'transparent',
        fillOpacity: 0,
        interactive: true,
      });
      const titre = p.libelle ?? 'Poste sans libellé';
      const relie = p.poste_libelle ? `SIRV2 : ${p.poste_libelle}` : 'Non relié à un poste SIRV2';
      zone.bindTooltip(`${titre}<br><span style="font-weight:400">${relie}</span>`, {
        sticky: true,
        className: 'schema-infobulle',
      });
      zone.on('click', () => this.posteClique.emit(p));
      zone.addTo(groupe);
      this.zones.set(p.id, zone);
    }
    groupe.addTo(carte);
    this.coucheZones = groupe;
    this.colorer();
  }

  private colorer(): void {
    const etats = this.etats();
    for (const [id, zone] of this.zones) {
      const etat = etats.get(id);
      if (etat) {
        const c = COULEURS[etat];
        zone.setStyle({ color: c.couleur, fillColor: c.couleur, fillOpacity: c.fond, weight: 2 });
      } else {
        zone.setStyle({ color: 'transparent', fillColor: 'transparent', fillOpacity: 0, weight: 1.5 });
      }
    }
  }

  private dessinerTrace(): void {
    const carte = this.carte;
    if (!carte) return;
    this.coucheTrace?.remove();
    this.coucheTrace = null;
    const points = this.trace();
    if (!this.schema() || points.length < 2) return;
    this.coucheTrace = L.polyline(
      points.map(([x, y]) => this.ll(x, y)),
      { color: '#e6007e', weight: 6, opacity: 0.55, interactive: false, renderer: this.rendu },
    ).addTo(carte);
  }
}
