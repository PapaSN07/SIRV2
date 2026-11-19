import { AfterViewInit, Component, ElementRef, OnDestroy, OnInit, ViewChild, computed, inject, signal } from '@angular/core';
import { DatePipe, DecimalPipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import * as L from 'leaflet';
import { SigAdminService } from '../services/sig-admin.service';
import {
  Defauts100Km,
  FeederSig,
  NoeudSigAdmin,
  SigListeParams,
  StationSig,
  SyntheseSig,
  TronconSigAdmin,
} from '../../../shared/models/sig.models';
import { PageHeaderComponent } from '../../../shared/ui/page-header/page-header.component';
import { AdminNavComponent } from '../../../shared/ui/admin-nav/admin-nav.component';
import { PaginatorComponent } from '../../../shared/ui/paginator/paginator.component';

type OngletSig = 'synthese' | 'defauts' | 'stations' | 'feeders' | 'troncons' | 'noeuds' | 'carte';

const ONGLETS: { id: OngletSig; libelle: string; icone: string }[] = [
  { id: 'synthese', libelle: 'Synthèse', icone: 'dashboard' },
  { id: 'defauts', libelle: 'Défauts aux 100 km', icone: 'query_stats' },
  { id: 'stations', libelle: 'Postes sources SIG', icone: 'domain' },
  { id: 'feeders', libelle: 'Feeders SIG', icone: 'cable' },
  { id: 'troncons', libelle: 'Tronçons SIG', icone: 'timeline' },
  { id: 'noeuds', libelle: 'Nœuds', icone: 'hub' },
  { id: 'carte', libelle: 'Localisation', icone: 'map' },
];

const COULEURS = ['#5b2a9e', '#e6007e', '#f58220', '#1e9e6a', '#2e3192', '#e5484d', '#fdb913', '#7a1fa2'];

/** Administration → SIG : consultation de la topologie importée du SIG (lecture seule). */
@Component({
  selector: 'sir-sig-admin',
  standalone: true,
  imports: [FormsModule, DatePipe, DecimalPipe, PageHeaderComponent, AdminNavComponent, PaginatorComponent],
  templateUrl: './sig-admin.component.html',
  styleUrl: './sig-admin.component.scss',
})
export class SigAdminComponent implements OnInit, AfterViewInit, OnDestroy {
  private readonly sig = inject(SigAdminService);

  readonly onglets = ONGLETS;
  readonly onglet = signal<OngletSig>('synthese');
  readonly pageSize = 20;
  readonly page = signal(1);
  readonly total = signal(0);
  readonly recherche = signal('');
  readonly tri = signal('');
  readonly loading = signal(false);
  readonly error = signal<string | null>(null);

  // Filtres
  readonly filtreFeeder = signal('');
  readonly filtreStation = signal('');
  readonly filtreCategorie = signal('');
  readonly filtreLocalisation = signal<'' | 'localise' | 'non_localise'>('');
  readonly filtreRattachement = signal<'' | 'rattache' | 'non_rattache'>('');

  readonly synthese = signal<SyntheseSig | null>(null);
  readonly stations = signal<StationSig[]>([]);
  readonly feeders = signal<FeederSig[]>([]);
  readonly troncons = signal<TronconSigAdmin[]>([]);
  readonly noeuds = signal<NoeudSigAdmin[]>([]);

  // Défauts aux 100 km
  readonly annees = [new Date().getFullYear(), new Date().getFullYear() - 1, new Date().getFullYear() - 2];
  readonly moisListe = ['Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin', 'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre'];
  readonly defautsAnnee = signal(new Date().getFullYear());
  readonly defautsMois = signal<number | null>(null);
  readonly defauts = signal<Defauts100Km | null>(null);
  readonly defautsVue = signal<'service' | 'feeder' | 'nature'>('service');
  readonly defautsFiltre = signal('');
  readonly feedersDefautsFiltres = computed(() => {
    const t = this.defautsFiltre().trim().toLowerCase();
    const lignes = this.defauts()?.par_feeder ?? [];
    return t ? lignes.filter((l) => (l.libelle + ' ' + (l.detail ?? '')).toLowerCase().includes(t)) : lignes;
  });
  readonly maxNature = computed(() => Math.max(1, ...(this.defauts()?.par_nature ?? []).map((n) => n.defauts)));

  // Carte
  readonly carteCible = signal<{ nom_feeder?: string; station?: string } | null>(null);
  readonly carteNoeuds = signal<NoeudSigAdmin[]>([]);
  readonly carteLegende = signal<{ categorie: string; couleur: string; nombre: number }[]>([]);
  readonly carteSaisie = signal('');
  @ViewChild('carte') private carteElement?: ElementRef<HTMLDivElement>;
  private carte: L.Map | null = null;
  private couche: L.LayerGroup | null = null;
  private delai: ReturnType<typeof setTimeout> | null = null;

  ngOnInit(): void {
    this.charger();
  }

  ngAfterViewInit(): void {
    this.initCarte();
  }

  ngOnDestroy(): void {
    this.carte?.remove();
  }

  changerOnglet(onglet: OngletSig): void {
    this.onglet.set(onglet);
    this.page.set(1);
    this.recherche.set('');
    this.tri.set('');
    this.error.set(null);
    if (onglet === 'carte') {
      setTimeout(() => this.initCarte());
      return;
    }
    this.charger();
  }

  onRecherche(texte: string): void {
    this.recherche.set(texte);
    if (this.delai) clearTimeout(this.delai);
    this.delai = setTimeout(() => {
      this.page.set(1);
      this.charger();
    }, 300);
  }

  appliquerFiltres(): void {
    this.page.set(1);
    this.charger();
  }

  reinitialiserFiltres(): void {
    this.filtreFeeder.set('');
    this.filtreStation.set('');
    this.filtreCategorie.set('');
    this.filtreLocalisation.set('');
    this.filtreRattachement.set('');
    this.appliquerFiltres();
  }

  onPage(page: number): void {
    this.page.set(page);
    this.charger();
  }

  trier(colonne: string): void {
    this.tri.set(this.tri() === colonne ? '-' + colonne : colonne);
    this.page.set(1);
    this.charger();
  }

  iconeTri(colonne: string): string {
    if (this.tri() === colonne) return 'arrow_upward';
    if (this.tri() === '-' + colonne) return 'arrow_downward';
    return 'unfold_more';
  }

  /** Depuis une ligne : voir les tronçons / nœuds d'un départ ou d'une station. */
  voirTroncons(nomFeeder: string): void {
    this.filtreFeeder.set(nomFeeder);
    this.changerOnglet('troncons');
  }

  voirNoeuds(filtre: { nom_feeder?: string; station?: string; categorie?: string }): void {
    this.filtreFeeder.set(filtre.nom_feeder ?? '');
    this.filtreStation.set(filtre.station ?? '');
    this.filtreCategorie.set(filtre.categorie ?? '');
    this.changerOnglet('noeuds');
  }

  voirCarte(cible: { nom_feeder?: string; station?: string }): void {
    this.carteSaisie.set(cible.nom_feeder ?? cible.station ?? '');
    this.changerOnglet('carte');
    this.chargerCarte(cible);
  }

  rechercherCarte(type: 'feeder' | 'station'): void {
    const valeur = this.carteSaisie().trim();
    if (!valeur) return;
    this.chargerCarte(type === 'feeder' ? { nom_feeder: valeur } : { station: valeur });
  }

  changerPeriodeDefauts(annee: number, mois: number | null): void {
    this.defautsAnnee.set(annee);
    this.defautsMois.set(mois);
    this.charger();
  }

  pourcentage(n: number, total: number): number {
    return total > 0 ? Math.round((n / total) * 1000) / 10 : 0;
  }

  private params(): SigListeParams {
    return {
      page: this.page(),
      page_size: this.pageSize,
      q: this.recherche(),
      tri: this.tri() || undefined,
      nom_feeder: this.filtreFeeder() || undefined,
      station: this.filtreStation() || undefined,
      categorie: this.filtreCategorie() || undefined,
      localisation: this.filtreLocalisation() || undefined,
      rattachement: this.filtreRattachement() || undefined,
    };
  }

  private charger(): void {
    const onglet = this.onglet();
    if (onglet === 'carte') return;
    this.loading.set(true);
    this.error.set(null);
    const erreur = (err: Error) => {
      this.error.set(err.message);
      this.loading.set(false);
    };
    const fin = () => this.loading.set(false);
    const p = this.params();
    switch (onglet) {
      case 'defauts':
        this.sig
          .defauts100km({ annee: this.defautsAnnee(), mois: this.defautsMois() ?? undefined })
          .subscribe({ next: (d) => (this.defauts.set(d), fin()), error: erreur });
        break;
      case 'synthese':
        this.sig.synthese().subscribe({ next: (s) => (this.synthese.set(s), fin()), error: erreur });
        break;
      case 'stations':
        this.sig.stations(p).subscribe({ next: (r) => (this.stations.set(r.items), this.total.set(r.total), fin()), error: erreur });
        break;
      case 'feeders':
        this.sig.feeders(p).subscribe({ next: (r) => (this.feeders.set(r.items), this.total.set(r.total), fin()), error: erreur });
        break;
      case 'troncons':
        this.sig.troncons(p).subscribe({ next: (r) => (this.troncons.set(r.items), this.total.set(r.total), fin()), error: erreur });
        break;
      case 'noeuds':
        this.sig.noeuds(p).subscribe({ next: (r) => (this.noeuds.set(r.items), this.total.set(r.total), fin()), error: erreur });
        break;
    }
  }

  private initCarte(): void {
    if (this.carte || !this.carteElement) return;
    this.carte = L.map(this.carteElement.nativeElement, { minZoom: 6, maxZoom: 19 }).fitBounds([
      [12.2, -17.6],
      [16.75, -11.3],
    ]);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '© OpenStreetMap',
    }).addTo(this.carte);
    L.control.scale({ imperial: false }).addTo(this.carte);
    this.couche = L.layerGroup().addTo(this.carte);
    new ResizeObserver(() => this.carte?.invalidateSize()).observe(this.carteElement.nativeElement);
    this.dessiner();
  }

  private chargerCarte(cible: { nom_feeder?: string; station?: string }): void {
    this.carteCible.set(cible);
    this.loading.set(true);
    this.error.set(null);
    this.sig.carte(cible).subscribe({
      next: (noeuds) => {
        this.carteNoeuds.set(noeuds);
        this.loading.set(false);
        this.dessiner();
      },
      error: (err: Error) => {
        this.error.set(err.message);
        this.loading.set(false);
      },
    });
  }

  private dessiner(): void {
    if (!this.carte || !this.couche) return;
    this.couche.clearLayers();
    const noeuds = this.carteNoeuds().filter((n) => n.latitude !== null && n.longitude !== null);
    const couleurs = new Map<string, string>();
    const comptes = new Map<string, number>();
    for (const n of noeuds) {
      const cat = n.categorie ?? '(sans catégorie)';
      if (!couleurs.has(cat)) couleurs.set(cat, COULEURS[couleurs.size % COULEURS.length]);
      comptes.set(cat, (comptes.get(cat) ?? 0) + 1);
      L.circleMarker([n.latitude!, n.longitude!], {
        radius: 5,
        color: '#ffffff',
        weight: 1,
        fillColor: couleurs.get(cat),
        fillOpacity: 0.9,
      })
        .bindTooltip(this.echapper(n.nom ?? '(sans nom)'), { direction: 'top' })
        .bindPopup(
          [
            `<strong>${this.echapper(n.nom ?? '(sans nom)')}</strong>`,
            `Catégorie : ${this.echapper(cat)}`,
            n.nom_feeder ? `Feeder : ${this.echapper(n.nom_feeder)}` : '',
            n.station ? `Station : ${this.echapper(n.station)}` : '',
            `${n.latitude!.toFixed(5)}, ${n.longitude!.toFixed(5)}`,
          ]
            .filter(Boolean)
            .join('<br>'),
        )
        .addTo(this.couche);
    }
    this.carteLegende.set([...couleurs.entries()].map(([categorie, couleur]) => ({ categorie, couleur, nombre: comptes.get(categorie) ?? 0 })));
    if (noeuds.length > 0) {
      this.carte.fitBounds(L.latLngBounds(noeuds.map((n) => [n.latitude!, n.longitude!] as L.LatLngTuple)).pad(0.1), {
        maxZoom: 16,
      });
    }
  }

  private echapper(texte: string): string {
    return texte.replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]!);
  }
}
