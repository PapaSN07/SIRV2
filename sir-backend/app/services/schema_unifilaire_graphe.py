"""Graphe d'un schéma unifilaire : postes situés entre deux postes.

Le graphe vient de l'import du PDF AutoCAD (scripts/migration/import_schema_unifilaire.py) :
nœuds = postes, organes et jonctions ; arêtes = tronçons de ligne, longueur en points.

« Entre deux postes A et B » :
- les postes du plus court chemin de A à B (le long de la ligne), dans l'ordre ;
- les postes en antenne : branche qui ne repart que d'un nœud intérieur au chemin et ne porte
  qu'un poste (schémas régionaux : postes H61 piqués sur la ligne) ;
- les dérivations plus longues qui ne repartent que de l'intérieur du chemin : proposées à part,
  non cochées (elles sont aussi isolées si l'on coupe en A et en B, mais l'opérateur choisit) ;
- une branche qui rejoint le réseau au-delà de A ou de B n'est pas « entre » les deux.
Pur Python, sans base : testable et mis en cache par schéma.
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass, field

DERIVATION_MAX_POSTES = 60


@dataclass
class Graphe:
    coords: list[tuple[float, float]]
    voisins: list[dict[int, float]]
    noeud_des_postes: list[int]  # poste (ordre de schema_unifilaire_postes.rang) → nœud
    postes_du_noeud: dict[int, list[int]] = field(default_factory=dict)

    @classmethod
    def depuis_json(cls, donnees: dict) -> Graphe:
        coords = [(float(x), float(y)) for x, y in donnees["coords"]]
        voisins: list[dict[int, float]] = [{} for _ in coords]
        for a, b, longueur in donnees["aretes"]:
            if longueur < voisins[a].get(b, float("inf")):
                voisins[a][b] = float(longueur)
                voisins[b][a] = float(longueur)
        postes = [int(n) for n in donnees["postes"]]
        par_noeud: dict[int, list[int]] = {}
        for rang, n in enumerate(postes):
            if n >= 0:
                par_noeud.setdefault(n, []).append(rang)
        return cls(coords=coords, voisins=voisins, noeud_des_postes=postes, postes_du_noeud=par_noeud)

    def chemin(self, depart: int, arrivee: int) -> list[int] | None:
        """Plus court chemin (Dijkstra, longueur des tronçons) entre deux nœuds."""
        if depart == arrivee:
            return [depart]
        dist = {depart: 0.0}
        prec: dict[int, int] = {}
        tas = [(0.0, depart)]
        while tas:
            d, u = heapq.heappop(tas)
            if u == arrivee:
                break
            if d > dist[u]:
                continue
            for v, longueur in self.voisins[u].items():
                nd = d + longueur
                if nd < dist.get(v, float("inf")):
                    dist[v] = nd
                    prec[v] = u
                    heapq.heappush(tas, (nd, v))
        if arrivee not in dist:
            return None
        trajet = [arrivee]
        while trajet[-1] != depart:
            trajet.append(prec[trajet[-1]])
        return trajet[::-1]


@dataclass
class Derivation:
    depuis_rang: int | None  # poste du chemin le plus proche de la dérivation (repère)
    rangs: list[int]


@dataclass
class ResultatEntre:
    rangs_chemin: list[int]  # postes du chemin, dans l'ordre, A et B compris
    rangs_antennes: list[int]  # postes seuls piqués sur le chemin
    derivations: list[Derivation]
    postes_hors_limite: int  # dérivations trop grandes, non proposées
    trace: list[tuple[float, float]]  # coordonnées du chemin (surlignage)


def postes_entre(graphe: Graphe, rang_a: int, rang_b: int) -> ResultatEntre | None:
    """Postes entre deux postes (rangs) ; None si aucune ligne ne les relie sur le schéma."""
    na, nb = graphe.noeud_des_postes[rang_a], graphe.noeud_des_postes[rang_b]
    trajet = graphe.chemin(na, nb)
    if trajet is None:
        return None
    sur_chemin = set(trajet)
    interieur = sur_chemin - {na, nb}

    rangs_chemin: list[int] = []
    for n in trajet:
        for rang in graphe.postes_du_noeud.get(n, ()):
            if rang not in rangs_chemin:
                rangs_chemin.append(rang)

    antennes: list[int] = []
    derivations: list[Derivation] = []
    hors_limite = 0
    vus: set[int] = set()
    dernier_poste: int | None = None
    for u in trajet[1:-1]:
        if graphe.postes_du_noeud.get(u):
            dernier_poste = graphe.postes_du_noeud[u][0]
        for depart in graphe.voisins[u]:
            if depart in sur_chemin or depart in vus:
                continue
            composante = {depart}
            pile = [depart]
            touche: set[int] = set()
            while pile:
                x = pile.pop()
                for y in graphe.voisins[x]:
                    if y in sur_chemin:
                        touche.add(y)
                    elif y not in composante:
                        composante.add(y)
                        pile.append(y)
            vus |= composante
            if not touche <= interieur:
                continue  # rejoint le réseau au-delà de A ou de B
            rangs = sorted(r for n in composante for r in graphe.postes_du_noeud.get(n, ()))
            if not rangs:
                continue
            if len(rangs) == 1:
                antennes.append(rangs[0])
            elif len(rangs) <= DERIVATION_MAX_POSTES:
                derivations.append(Derivation(depuis_rang=dernier_poste, rangs=rangs))
            else:
                hors_limite += len(rangs)
    return ResultatEntre(
        rangs_chemin=rangs_chemin,
        rangs_antennes=antennes,
        derivations=derivations,
        postes_hors_limite=hors_limite,
        trace=[graphe.coords[n] for n in trajet],
    )
