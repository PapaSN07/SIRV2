"""Lecture d'un schéma unifilaire AutoCAD (PDF vectoriel) : postes, libellés, graphe, tuiles.

Le PDF est un tracé AutoCAD : chaque poste est un petit carré ou un cercle, son nom est un texte
posé à côté (parfois relié par un trait de rappel), les lignes sont des segments qui finissent sur
le bord des symboles, se raccordent en T ou passent à travers les organes (IAT, flèches…).

On en tire :
- les postes (symbole + libellé) ;
- un graphe : nœuds = postes, organes et jonctions ; arêtes = tronçons de ligne (longueur en points).
  Deux lignes qui se croisent sans raccord (croisement « X ») ne sont pas reliées ;
- les tuiles PNG 256 × 256 de l'affichage (Leaflet, CRS.Simple), de 1 point = 2 px (zoom max)
  jusqu'au schéma entier sur une tuile.

Dépendance : PyMuPDF (pip install pymupdf), sur le poste qui lance l'import uniquement : l'API SIRV2 ne
lit que les données produites.
"""

from __future__ import annotations

import collections
import io
import math
import re
from collections.abc import Iterator
from dataclasses import dataclass, field

TOL_JONCTION = 1.6  # extrémités rapprochées : même nœud (points PDF)
TOL_T = 1.0  # extrémité posée sur un autre segment : raccord en T
LONGUEUR_MIN = 2.5  # plus court : hachures et dégradés des symboles
TAILLE_TUILE = 256
ECHELLE_MAX = 2.0  # pixels par point au zoom maximal

# Textes qui ne sont pas des noms de poste (marques de cellule, puissances, sigles d'organes)
_BRUIT = re.compile(r"^(CM|CO|C|I|P|T|ST|IAT|IACT|DRR|RA|\(?\s*\d+[.,]?\d*\s*(kva|mva|kv|mm²|mm2)?\s*\)?)$", re.I)
_PUISSANCE = re.compile(r"\(?\s*(\d+)\s*kva\s*\)?", re.I)


@dataclass
class Symbole:
    x0: float
    y0: float
    x1: float
    y1: float
    forme: str  # carre | rond | organe
    libelle: str | None = None
    libelle_bbox: tuple[float, float, float, float] | None = None
    puissance_kva: int | None = None
    noeud: int = -1


@dataclass
class SchemaExtrait:
    largeur: float
    hauteur: float
    postes: list[Symbole]
    coords: list[tuple[float, float]]  # coordonnées des nœuds du graphe
    aretes: list[tuple[int, int, float]]
    stats: dict[str, int] = field(default_factory=dict)

    def graphe_json(self) -> dict[str, object]:
        """Graphe compact enregistré en base (gzip) et lu par l'API."""
        return {
            "v": 1,
            "coords": [[round(x, 1), round(y, 1)] for x, y in self.coords],
            "aretes": [[a, b, round(L, 1)] for a, b, L in self.aretes],
            "postes": [p.noeud for p in self.postes],
        }


def _centre(b: tuple[float, float, float, float]) -> tuple[float, float]:
    return (b[0] + b[2]) / 2, (b[1] + b[3]) / 2


def _cout_libelle(lab: tuple[float, float, float, float], sym: tuple[float, float, float, float]) -> float:
    """Écart entre un libellé et un symbole : au-dessus / au-dessous → centrés en x, à côté → en y."""
    dx = max(sym[0] - lab[2], lab[0] - sym[2], 0.0)
    dy = max(sym[1] - lab[3], lab[1] - sym[3], 0.0)
    dcx = abs((lab[0] + lab[2]) - (sym[0] + sym[2])) / 2
    dcy = abs((lab[1] + lab[3]) - (sym[1] + sym[3])) / 2
    if dy >= dx:
        return dy + 0.8 * max(0.0, dcx - (sym[2] - sym[0]) / 2)
    return dx + 0.8 * max(0.0, dcy - (sym[3] - sym[1]) / 2)


class _Grille:
    """Index spatial simple (cases carrées) pour les recherches de voisinage."""

    def __init__(self, pas: float) -> None:
        self.pas = pas
        self.cases: dict[tuple[int, int], list[int]] = collections.defaultdict(list)

    def ajouter(self, i: int, x0: float, y0: float, x1: float, y1: float) -> None:
        p = self.pas
        for gx in range(int(x0 // p), int(x1 // p) + 1):
            for gy in range(int(y0 // p), int(y1 // p) + 1):
                self.cases[(gx, gy)].append(i)

    def autour(self, x0: float, y0: float, x1: float, y1: float) -> Iterator[int]:
        p = self.pas
        vus: set[int] = set()
        for gx in range(int(x0 // p), int(x1 // p) + 1):
            for gy in range(int(y0 // p), int(y1 // p) + 1):
                for i in self.cases.get((gx, gy), ()):
                    if i not in vus:
                        vus.add(i)
                        yield i


Segment = tuple[float, float, float, float]


def _lire_dessins(page) -> tuple[list[Symbole], list[Segment], list[Segment]]:  # noqa: ANN001
    """Symboles, segments de ligne et traits de rappel (fins triangles noirs pleins d'AutoCAD)."""
    symboles: list[Symbole] = []
    segments: list[Segment] = []
    rappels: list[Segment] = []
    for d in page.get_drawings():
        items = d["items"]
        kinds = "".join(i[0] for i in items)
        r = d["rect"]
        w, h = r.width, r.height
        if d["type"] in ("f", "fs") and set(kinds) == {"l"} and min(w, h) <= 2.5 and max(w, h) >= 8:
            # trait de rappel : extrémités de la plus grande diagonale du boîtier
            pts = [p for it in items for p in it[1:]]
            a, b = max(((p, q) for p in pts for q in pts), key=lambda pq: (pq[0].x - pq[1].x) ** 2 + (pq[0].y - pq[1].y) ** 2)
            rappels.append((a.x, a.y, b.x, b.y))
            continue
        if d["type"] == "s" and kinds == "qu" and 7.5 <= w <= 70 and 7.5 <= h <= 45:
            symboles.append(Symbole(r.x0, r.y0, r.x1, r.y1, "carre"))
            continue
        if d["type"] == "s" and kinds in ("cccc", "cccccccc") and 7.5 <= w <= 25 and abs(w - h) < 2:
            symboles.append(Symbole(r.x0, r.y0, r.x1, r.y1, "rond"))
            continue
        # organes (IAT, flèches de sens, croix…) : formes fermées que la ligne traverse
        if 4 <= w <= 40 and 4 <= h <= 40 and (d.get("fill") is not None or d.get("closePath")) and len(items) >= 3:
            symboles.append(Symbole(r.x0, r.y0, r.x1, r.y1, "organe"))
            continue
        if d["type"] != "s":
            continue
        for it in items:
            if it[0] == "l":
                a, b = it[1], it[2]
            elif it[0] == "c":
                a, b = it[1], it[4]
            else:
                continue
            if math.hypot(b.x - a.x, b.y - a.y) >= LONGUEUR_MIN:
                segments.append((a.x, a.y, b.x, b.y))
    return symboles, segments, rappels


def _sans_imbrication(symboles: list[Symbole]) -> tuple[list[Symbole], _Grille]:
    """Un symbole posé dans un autre (cellules d'un grand poste) : on garde l'enveloppe."""
    symboles = sorted(symboles, key=lambda s: -(s.x1 - s.x0) * (s.y1 - s.y0))
    grille = _Grille(60)
    gardes: list[Symbole] = []
    for s in symboles:
        cx, cy = (s.x0 + s.x1) / 2, (s.y0 + s.y1) / 2
        if any(
            gardes[k].x0 - 1 <= cx <= gardes[k].x1 + 1 and gardes[k].y0 - 1 <= cy <= gardes[k].y1 + 1
            for k in grille.autour(cx, cy, cx, cy)
        ):
            continue
        gardes.append(s)
        grille.ajouter(len(gardes) - 1, s.x0 - 1, s.y0 - 1, s.x1 + 1, s.y1 + 1)
    return gardes, grille


def _lire_libelles(page) -> list[tuple[str, tuple[float, float, float, float]]]:  # noqa: ANN001
    """Lignes de texte regroupées en libellés (même sens, même taille, l'une sous l'autre, alignées)."""
    brutes: list[tuple[str, tuple[float, float, float, float], float, bool]] = []
    for b in page.get_text("dict")["blocks"]:
        for ligne in b.get("lines", []):
            txt = " ".join(s["text"].strip() for s in ligne["spans"] if s["text"].strip())
            if txt:
                taille = max(s["size"] for s in ligne["spans"])
                brutes.append((txt, tuple(ligne["bbox"]), taille, abs(ligne["dir"][0]) < 0.5))
    parent = list(range(len(brutes)))

    def racine(a: int) -> int:
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    grille = _Grille(40)
    for i, (_, b, _, _) in enumerate(brutes):
        grille.ajouter(i, b[0], b[1], b[0], b[1])
    for i, (_, b, sz, vert) in enumerate(brutes):
        for j in grille.autour(b[0] - 40, b[1] - 40, b[2] + 40, b[3] + 40):
            if j <= i:
                continue
            _, b2, sz2, vert2 = brutes[j]
            if vert != vert2 or abs(sz - sz2) > 0.25 * sz:
                continue
            if not vert:
                ecart = max(b2[1] - b[3], b[1] - b2[3])
                a0, a1, c0, c1 = b[0], b[2], b2[0], b2[2]
            else:
                ecart = max(b2[0] - b[2], b[0] - b2[2])
                a0, a1, c0, c1 = b[1], b[3], b2[1], b2[3]
            chevauchement = min(a1, c1) - max(a0, c0)
            aligne = (
                abs((a0 + a1) - (c0 + c1)) / 2 <= 0.15 * max(a1 - a0, c1 - c0) + 2
                or abs(a0 - c0) <= 0.5 * sz
                or abs(a1 - c1) <= 0.5 * sz
            )
            if ecart <= 0.45 * sz and chevauchement > 0.3 * sz and aligne:
                parent[racine(i)] = racine(j)
    groupes: dict[int, list[int]] = collections.defaultdict(list)
    for i in range(len(brutes)):
        groupes[racine(i)].append(i)
    libelles: list[tuple[str, tuple[float, float, float, float]]] = []
    for ids in groupes.values():
        vert = brutes[ids[0]][3]
        ids.sort(key=lambda i: brutes[i][1][0] if vert else brutes[i][1][1])
        lignes = [brutes[i] for i in ids if not _BRUIT.match(brutes[i][0].strip())]
        if not lignes:
            continue
        texte = " ".join(re.sub(r"^(CM|C)\s+", "", t[0]) for t in lignes)
        texte = re.sub(r"\s+", " ", texte).strip()
        texte = re.sub(r"\s+C$", "", texte)  # marque de cellule « C » collée au nom
        if len(texte) < 2:
            continue
        bbox = (
            min(t[1][0] for t in lignes),
            min(t[1][1] for t in lignes),
            max(t[1][2] for t in lignes),
            max(t[1][3] for t in lignes),
        )
        libelles.append((texte, bbox))
    return libelles


def _associer_libelles(
    postes: list[Symbole],
    libelles: list[tuple[str, tuple[float, float, float, float]]],
    segments: list[tuple[float, float, float, float]],
) -> int:
    """Chaque poste reçoit au plus un libellé : traits de rappel d'abord, puis le plus proche."""
    grille = _Grille(60)
    for k, s in enumerate(postes):
        grille.ajouter(k, s.x0, s.y0, s.x1, s.y1)
    pris_lab: set[int] = set()

    def poser(i: int, k: int) -> None:
        texte, bbox = libelles[i]
        m = _PUISSANCE.search(texte)
        postes[k].puissance_kva = int(m.group(1)) if m else None
        postes[k].libelle = _PUISSANCE.sub("", texte).strip() or texte
        postes[k].libelle_bbox = bbox
        pris_lab.add(i)

    # 1. Traits de rappel : un segment qui part du libellé et finit sur un poste
    glab = _Grille(60)
    for i, (_, b) in enumerate(libelles):
        glab.ajouter(i, b[0] - 7, b[1] - 7, b[2] + 7, b[3] + 7)

    def poste_sous(x: float, y: float, tol: float = 4) -> int | None:
        for k in grille.autour(x, y, x, y):
            s = postes[k]
            if s.x0 - tol <= x <= s.x1 + tol and s.y0 - tol <= y <= s.y1 + tol:
                return k
        return None

    def libelle_sous(x: float, y: float) -> int | None:
        for i in glab.autour(x, y, x, y):
            b = libelles[i][1]
            if b[0] - 7 <= x <= b[2] + 7 and b[1] - 7 <= y <= b[3] + 7:
                return i
        return None

    rappels: list[tuple[float, int, int]] = []
    for x0, y0, x1, y1 in segments:
        if math.hypot(x1 - x0, y1 - y0) > 150:
            continue
        for (lx, ly), (px, py) in (((x0, y0), (x1, y1)), ((x1, y1), (x0, y0))):
            i = libelle_sous(lx, ly)
            k = poste_sous(px, py) if i is not None else None
            if i is not None and k is not None and libelle_sous(px, py) != i:
                rappels.append((math.hypot(x1 - x0, y1 - y0), i, k))
    for _, i, k in sorted(rappels):
        if i not in pris_lab and postes[k].libelle is None:
            poser(i, k)

    # 2. Le plus proche (affectation gloutonne par écart croissant)
    candidats: list[tuple[float, int, int]] = []
    for i, (_, b) in enumerate(libelles):
        if i in pris_lab:
            continue
        for k in grille.autour(b[0] - 45, b[1] - 45, b[2] + 45, b[3] + 45):
            if postes[k].libelle is not None:
                continue
            ecart = _cout_libelle(b, (postes[k].x0, postes[k].y0, postes[k].x1, postes[k].y1))
            if ecart <= 40:
                candidats.append((ecart, i, k))
    for _, i, k in sorted(candidats):
        if i not in pris_lab and postes[k].libelle is None:
            poser(i, k)
    return len(pris_lab)


def extraire(chemin_pdf: str) -> SchemaExtrait:
    import pymupdf

    doc = pymupdf.open(chemin_pdf)
    page = doc[0]
    symboles, segments, rappels = _lire_dessins(page)
    symboles, grille = _sans_imbrication(symboles)

    def symbole_de(x: float, y: float, tol: float = 1.5) -> int | None:
        for k in grille.autour(x, y, x, y):
            s = symboles[k]
            if s.x0 - tol <= x <= s.x1 + tol and s.y0 - tol <= y <= s.y1 + tol:
                return k
        return None

    # Segments internes à un symbole (hachures, dégradés, marques) : ignorés
    segments = [
        s for s in segments if not ((a := symbole_de(s[0], s[1], 0.2)) is not None and a == symbole_de(s[2], s[3], 0.2))
    ]

    # Raccords en T : l'extrémité d'un segment posée sur l'intérieur d'un autre le coupe
    gseg = _Grille(20)
    for i, (x0, y0, x1, y1) in enumerate(segments):
        gseg.ajouter(i, min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))
    coupes: dict[int, list[tuple[float, float, float]]] = collections.defaultdict(list)
    for i, (x0, y0, x1, y1) in enumerate(segments):
        for px, py in ((x0, y0), (x1, y1)):
            for j in gseg.autour(px, py, px, py):
                if j == i:
                    continue
                ax, ay, bx, by = segments[j]
                dx, dy = bx - ax, by - ay
                l2 = dx * dx + dy * dy
                if l2 == 0:
                    continue
                t = ((px - ax) * dx + (py - ay) * dy) / l2
                if 0.02 < t < 0.98 and math.hypot(px - (ax + t * dx), py - (ay + t * dy)) <= TOL_T:
                    coupes[j].append((t, px, py))
    morceaux: list[tuple[float, float, float, float]] = []
    for i, (x0, y0, x1, y1) in enumerate(segments):
        pts = [(x0, y0)] + [(px, py) for _, px, py in sorted(coupes.get(i, ()))] + [(x1, y1)]
        morceaux.extend((a[0], a[1], b[0], b[1]) for a, b in zip(pts, pts[1:]))

    # Nœuds : le symbole touché, sinon les extrémités rapprochées (union-find)
    parent: dict[tuple, tuple] = {}

    def racine(a: tuple) -> tuple:
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    points = _Grille(TOL_JONCTION)
    cles_points: list[tuple] = []

    def noeud(x: float, y: float) -> tuple:
        k = symbole_de(x, y)
        if k is not None:
            n: tuple = ("s", k)
            parent.setdefault(n, n)
            return n
        n = ("p", round(x, 1), round(y, 1))
        if n not in parent:
            parent[n] = n
            for m in points.autour(x - TOL_JONCTION, y - TOL_JONCTION, x + TOL_JONCTION, y + TOL_JONCTION):
                q = cles_points[m]
                if math.hypot(q[1] - x, q[2] - y) <= TOL_JONCTION:
                    ra, rb = racine(n), racine(q)
                    if ra != rb:
                        parent[ra] = rb
            cles_points.append(n)
            points.ajouter(len(cles_points) - 1, x, y, x, y)
        return n

    for k in range(len(symboles)):
        parent[("s", k)] = ("s", k)
    liens: dict[tuple, dict[tuple, float]] = collections.defaultdict(dict)
    for x0, y0, x1, y1 in morceaux:
        a, b = racine(noeud(x0, y0)), racine(noeud(x1, y1))
        if a == b:
            continue
        longueur = math.hypot(x1 - x0, y1 - y0)
        if longueur < liens[a].get(b, math.inf):
            liens[a][b] = longueur
            liens[b][a] = longueur

    # Numérotation : chaque poste a un nœud (même isolé), puis les autres nœuds utiles
    index: dict[tuple, int] = {}
    coords: list[tuple[float, float]] = []

    def numero(n: tuple) -> int:
        if n not in index:
            index[n] = len(coords)
            if n[0] == "s":
                s = symboles[n[1]]
                coords.append(((s.x0 + s.x1) / 2, (s.y0 + s.y1) / 2))
            else:
                coords.append((n[1], n[2]))
        return index[n]

    postes = [s for s in symboles if s.forme != "organe"]
    for k, s in enumerate(symboles):
        if s.forme != "organe":
            s.noeud = numero(racine(("s", k)))
    aretes: list[tuple[int, int, float]] = []
    for a, voisins in liens.items():
        for b, longueur in voisins.items():
            if repr(a) < repr(b):
                aretes.append((numero(a), numero(b), longueur))

    libelles = _lire_libelles(page)
    nommes = _associer_libelles(postes, libelles, rappels)
    return SchemaExtrait(
        largeur=page.rect.width,
        hauteur=page.rect.height,
        postes=postes,
        coords=coords,
        aretes=aretes,
        stats={
            "postes": len(postes),
            "postes_nommes": sum(1 for p in postes if p.libelle),
            "organes": sum(1 for s in symboles if s.forme == "organe"),
            "libelles": len(libelles),
            "libelles_associes": nommes,
            "noeuds": len(coords),
            "aretes": len(aretes),
        },
    )


def zoom_max(largeur: float, hauteur: float) -> int:
    """Zoom maximal Leaflet : au zoom 0, le schéma entier tient sur deux tuiles de large."""
    cote = max(largeur, hauteur) * ECHELLE_MAX
    return max(1, math.ceil(math.log2(cote / (2 * TAILLE_TUILE))))


def tuiles(chemin_pdf: str) -> Iterator[tuple[int, int, int, bytes]]:
    """Tuiles PNG (z, x, y, contenu) ; les tuiles entièrement blanches sont omises."""
    import pymupdf
    from PIL import Image

    doc = pymupdf.open(chemin_pdf)
    page = doc[0]
    liste = page.get_displaylist()
    largeur, hauteur = page.rect.width, page.rect.height
    zmax = zoom_max(largeur, hauteur)
    for z in range(zmax + 1):
        echelle = ECHELLE_MAX / (2 ** (zmax - z))
        larg_px = math.ceil(largeur * echelle)
        haut_px = math.ceil(hauteur * echelle)
        for ty in range(math.ceil(haut_px / TAILLE_TUILE)):
            y0 = ty * TAILLE_TUILE / echelle
            clip = pymupdf.Rect(0, y0, largeur, min(hauteur, y0 + TAILLE_TUILE / echelle))
            pix = liste.get_pixmap(matrix=pymupdf.Matrix(echelle, echelle), clip=clip, alpha=False)
            bande = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            for tx in range(math.ceil(larg_px / TAILLE_TUILE)):
                tuile = Image.new("RGB", (TAILLE_TUILE, TAILLE_TUILE), (255, 255, 255))
                gauche = tx * TAILLE_TUILE
                if gauche >= bande.width:
                    continue
                droite = min(bande.width, gauche + TAILLE_TUILE)
                tuile.paste(bande.crop((gauche, 0, droite, min(bande.height, TAILLE_TUILE))), (0, 0))
                if tuile.getextrema() == ((255, 255), (255, 255), (255, 255)):
                    continue
                tampon = io.BytesIO()
                tuile.quantize(colors=128, method=Image.Quantize.FASTOCTREE).save(tampon, "PNG", optimize=True)
                yield z, tx, ty, tampon.getvalue()
