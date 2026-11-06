"""Fichiers du rapport mensuel d'exploitation distribution : PDF, Word et Excel.

Mise en page reprise du modèle « Analyse succincte statistiques exploitation distribution »
(PR3-INS-108-a) avec la charte du rapport hebdomadaire DD : indicateurs du mois en tête, puis
les sections HTA du modèle, chacune avec son tableau et, quand il aide, son graphique.
Les tableaux sont calculés une fois (``Tableaux``) et servent aux trois formats.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from app.services.rapport_hebdo_dd_export import (
    AMBRE, DISCRET, LILAS, ORANGE, TEXTE, TEXTE_DOUX, TRAIT, TRAIT_LEGER, VERT, VIOLET, VIOLET_FONCE,
    VIOLET_MOYEN, _LOGO,
)
from app.services.rapport_hebdo_dd_service import DAKAR, REGIONS
from app.services.rapport_mensuel_dd_service import (
    FUGITIF,
    INCIDENTS,
    LIBELLES_NATURE,
    MOIS,
    NATURES,
    PERMANENT,
    SEMI_PERMANENT,
    Indicateur,
    RapportMensuelData,
)

REFERENCE = "Réf. : PR3-INS-108-a"
TITRE = "Analyse succincte des statistiques d'exploitation distribution"
COULEURS_NATURE = [VIOLET_FONCE, VIOLET, VIOLET_MOYEN, ORANGE, AMBRE, LILAS, "9C95A3"]
LIBELLE_TOP = {PERMANENT: "Permanent", SEMI_PERMANENT: "Semi-permanent", FUGITIF: "Fugitif"}
LIBELLE_COURT = {
    PERMANENT: "Permanent", SEMI_PERMANENT: "Semi-permanent", FUGITIF: "Fugitif",
    "delestage_hta": "Délestage incident HTA", "travaux_hta": "Travaux réseau HTA",
    "manoeuvre_hta": "Manœuvre réseau HTA", "autres_hta": "Autres coupures HTA",
}
_TRONCONS_MAX = 15
_SIEGES_COLONNES = 6


def nb(v: float | None, d: int = 0) -> str:
    if v is None:
        return "—"
    # espace insécable : un nombre n'est jamais coupé en fin de ligne
    return f"{v:,.{d}f}".replace(",", "\u00a0").replace(".", ",")


def kwh(mwh: float | None) -> str:
    return "—" if mwh is None else nb(mwh * 1000)


def pct(v: float | None, signe: bool = True) -> str:
    if v is None:
        return "—"
    return f"{'+' if signe and v > 0 else ''}{nb(v, 1)} %"


def ecart_txt(v: int) -> str:
    return f"+{v}" if v > 0 else str(v)


def tendance(v: float | None) -> str:
    if v is None:
        return "—"
    return "hausse" if v > 0.5 else "baisse" if v < -0.5 else "stable"


def valeur_indicateur(i: Indicateur, v: float | None) -> str:
    if v is None:
        return "—"
    if i.unite == "kWh":
        return nb(v)
    if i.unite == "h":
        return nb(v, 2)
    return nb(v, 3) if v < 50 else nb(v)


def nom_fichier(data: RapportMensuelData) -> str:
    return f"Analyse succincte exploitation distribution {MOIS[data.mois - 1]} {data.annee}"


# --------------------------------------------------------------------------------------
# Tableaux communs (lignes de texte)
# --------------------------------------------------------------------------------------


@dataclass
class Tableaux:
    indicateurs: list[list[str]]
    realisations: list[list[str]]
    recap_services: list[list[str]]
    evolution_m1: list[list[str]]
    evolution_n1: list[list[str]]
    tops: list[tuple[str, list[list[str]]]]  # (titre, lignes)
    top_des_tops: list[tuple[str, list[list[str]]]]
    sieges: list[tuple[str, list[list[str]]]]
    troncons: list[tuple[str, list[list[str]]]]
    programmes: list[list[str]]
    agressions: list[tuple[str, list[list[str]]]]
    defauts: list[list[str]]
    services_end: list[tuple[str, float, float | None]]  # (service, END MWh, cible MWh)
    natures_end: list[tuple[str, float]]


def construire_tableaux(d: RapportMensuelData) -> Tableaux:
    prec = d.periode_prec
    ind = [["Indicateur", "Réalisé", "Cible du mois", "Cumul de l'année", "Cible cumulée", "Commentaire"]]
    for i in d.indicateurs:
        u = f" {i.unite}" if i.unite else ""
        etat = "" if i.atteint is None else ("Cible atteinte" if i.atteint else "Cible dépassée")
        ind.append([
            i.libelle, valeur_indicateur(i, i.realise) + (u if i.realise is not None else ""),
            valeur_indicateur(i, i.cible), valeur_indicateur(i, i.cumul), valeur_indicateur(i, i.cible_cumul),
            " · ".join(t for t in (etat, i.note) if t),
        ])

    entete = ["Nature"]
    for z in d.zones:
        entete += [f"{z} nombre", f"{z} END (kWh)"]
    if len(d.zones) > 1:
        entete += ["Total nombre", "Total END (kWh)"]
    real = [entete]
    for cle in NATURES:
        ligne = [LIBELLES_NATURE[cle]]
        for z in d.zones:
            c = d.bilan.get(z, {}).get(cle)
            ligne += [nb(c.nombre if c else 0), kwh(c.end_mwh if c else 0)]
        if len(d.zones) > 1:
            t = d.total_nature(cle)
            ligne += [nb(t.nombre), kwh(t.end_mwh)]
        real.append(ligne)
    total = ["TOTAL"]
    for z in d.zones:
        t = d.total_zone(z)
        total += [nb(t.nombre), kwh(t.end_mwh)]
    if len(d.zones) > 1:
        total += [nb(d.total.nombre), kwh(d.total.end_mwh)]
    real.append(total)

    codes = [s.code for s in d.services]
    recap = [["Nature"] + codes + ["TOTAL"]]
    for cle in NATURES:
        vals = [s.par_nature.get(cle).nombre if s.par_nature.get(cle) else 0 for s in d.services]
        recap.append([LIBELLE_COURT[cle]] + [nb(v) for v in vals] + [nb(sum(vals))])
    recap.append(["END (kWh)"] + [kwh(s.total.end_mwh) for s in d.services] + [kwh(d.total.end_mwh)])

    def evol(lignes, lib_ref: str, lib_act: str) -> list[list[str]]:
        rows = [["Exploitation", "Service", f"Nombre {lib_ref}", f"Nombre {lib_act}", "Écart",
                 f"END {lib_ref} (kWh)", f"END {lib_act} (kWh)", "Évolution END"]]
        for z in d.zones:
            sous = [e for e in lignes if e.zone == z]
            for e in sous:
                rows.append([z, e.code, nb(e.nombre_prec), nb(e.nombre), ecart_txt(e.ecart),
                             kwh(e.end_prec_mwh), kwh(e.end_mwh), pct(e.evolution_pct)])
            np_, na = sum(e.nombre_prec for e in sous), sum(e.nombre for e in sous)
            ep, ea = sum(e.end_prec_mwh for e in sous), sum(e.end_mwh for e in sous)
            ev = 100 * (ea - ep) / ep if ep else None
            rows.append([f"Sous-total {z}", "", nb(np_), nb(na), ecart_txt(na - np_), kwh(ep), kwh(ea), pct(ev)])
        np_, na = sum(e.nombre_prec for e in lignes), sum(e.nombre for e in lignes)
        ep, ea = sum(e.end_prec_mwh for e in lignes), sum(e.end_mwh for e in lignes)
        ev = 100 * (ea - ep) / ep if ep else None
        rows.append(["Total", "", nb(np_), nb(na), ecart_txt(na - np_), kwh(ep), kwh(ea), pct(ev)])
        return rows

    a_prec = f"{MOIS[d.mois - 1][:4]}. {d.annee - 1}"
    m_prec = prec.split()[0][:4] + "."
    m_act = MOIS[d.mois - 1][:4] + "."

    def lignes_top(tops) -> list[list[str]]:
        rows = [["Départ", "Service(s)", m_prec, m_act, "Évol.", "Sièges principaux"]]
        for t in tops:
            sieges = ", ".join(f"{s} {n}" for s, n in list(t.sieges.items())[:4])
            rows.append([t.feeder, t.services, nb(t.nombre_prec), nb(t.nombre), ecart_txt(t.evolution), sieges])
        return rows

    tops = [
        (f"{z} — Top {len(d.tops[z][cle])} {LIBELLE_TOP[cle].lower()}", lignes_top(d.tops[z][cle]))
        for z in d.zones for cle in INCIDENTS if d.tops.get(z, {}).get(cle)
    ]
    tdt = [(f"{z} — Top des tops (permanent, semi-permanent, fugitif)", lignes_top(d.top_des_tops[z]))
           for z in d.zones if d.top_des_tops.get(z)]

    sieges = []
    for z in d.zones:
        par = d.sieges_permanents.get(z, {})
        if not par:
            continue
        totaux: dict[str, int] = {}
        for compte in par.values():
            for siege, n in compte.items():
                totaux[siege] = totaux.get(siege, 0) + n
        colonnes = sorted(totaux, key=lambda k: -totaux[k])[:_SIEGES_COLONNES]
        autres = len(totaux) > len(colonnes)
        rows = [["Service"] + colonnes + (["Autres"] if autres else []) + ["Total"]]
        for code, compte in par.items():
            reste = sum(n for k, n in compte.items() if k not in colonnes)
            rows.append([code] + [nb(compte.get(c, 0)) for c in colonnes] + ([nb(reste)] if autres else [])
                        + [nb(sum(compte.values()))])
        reste = sum(n for k, n in totaux.items() if k not in colonnes)
        rows.append(["Total"] + [nb(totaux[c]) for c in colonnes] + ([nb(reste)] if autres else [])
                    + [nb(sum(totaux.values()))])
        sieges.append((f"Sièges présumés des défauts permanents — {z}", rows))

    troncons = [
        (f"Tronçons fragilisés — {z}", [["Service", "Départ", "Tronçon / antenne", "Défauts", "Siège dominant"]]
         + [[t.service, t.feeder, t.troncon, nb(t.nombre), t.siege] for t in d.troncons[z][:_TRONCONS_MAX]])
        for z in d.zones if d.troncons.get(z)
    ]
    programmes = [["Service", "Coupures pour travaux", "END (kWh)"]] + [
        [code, nb(c.nombre), kwh(c.end_mwh)] for code, c in d.programmes.items()
    ]
    if len(programmes) > 1:
        programmes.append(["Total", nb(sum(c.nombre for c in d.programmes.values())),
                           kwh(sum(c.end_mwh for c in d.programmes.values()))])
    agressions = []
    for z in d.zones:
        lst = d.agressions.get(z, [])
        if lst:
            rows = [["Service(s)", "Entreprise agresseuse", "Agressions", "END (kWh)"]]
            rows += [[a.services, a.entreprise, nb(a.nombre), kwh(a.end_mwh)] for a in lst]
            rows.append(["Total", "", nb(sum(a.nombre for a in lst)), kwh(sum(a.end_mwh for a in lst))])
            agressions.append((f"Agressions — {z}", rows))
    defauts = [["Service", "Défauts permanents", "Longueur HTA (km)", "Défauts aux 100 km"]] + [
        [x.code, nb(x.permanents), nb(x.longueur_km), nb(x.valeur, 2)] for x in d.defauts
    ]
    return Tableaux(
        indicateurs=ind, realisations=real, recap_services=recap,
        evolution_m1=evol(d.evolution_m1, m_prec, m_act),
        evolution_n1=evol(d.evolution_n1, a_prec, f"{m_act} {d.annee}"),
        tops=tops, top_des_tops=tdt, sieges=sieges, troncons=troncons, programmes=programmes,
        agressions=agressions, defauts=defauts,
        services_end=[(s.code, s.total.end_mwh, d.cibles_service_mwh.get(s.code)) for s in d.services],
        natures_end=[(LIBELLES_NATURE[c], d.total_nature(c).end_mwh) for c in NATURES],
    )


# --------------------------------------------------------------------------------------
# PDF
# --------------------------------------------------------------------------------------


def exporter_pdf(chemin: Path, d: RapportMensuelData) -> None:
    from reportlab.graphics.charts.barcharts import VerticalBarChart
    from reportlab.graphics.charts.legends import Legend
    from reportlab.graphics.charts.lineplots import LinePlot
    from reportlab.graphics.charts.piecharts import Pie
    from reportlab.graphics.shapes import Drawing, String
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_RIGHT
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        BaseDocTemplate, CondPageBreak, Frame, Image, KeepTogether, NextPageTemplate, PageBreak, PageTemplate,
        Paragraph, Spacer, Table, TableStyle,
    )

    from app.services.rapport_export_pdf_service import dessiner_carte_end

    t = construire_tableaux(d)
    C = lambda h: colors.HexColor(f"#{h}")  # noqa: E731
    L = 18.0 * cm

    def st(nom: str, **kw) -> ParagraphStyle:
        base = dict(fontName="Helvetica", fontSize=8.5, leading=11.5, textColor=C(TEXTE))
        base.update(kw)
        return ParagraphStyle(nom, **base)

    sur = st("sur", fontName="Helvetica-Bold", fontSize=7.5, textColor=C(VIOLET), spaceAfter=3)
    h1 = st("h1", fontName="Helvetica-Bold", fontSize=20, leading=24, spaceAfter=4)
    per = st("per", fontSize=9, textColor=C(DISCRET), spaceAfter=10)
    h2 = st("h2", fontName="Helvetica-Bold", fontSize=12.5, leading=16, textColor=C(VIOLET_FONCE),
            spaceBefore=14, spaceAfter=6)
    h3 = st("h3", fontName="Helvetica-Bold", fontSize=9.5, leading=12, spaceBefore=8, spaceAfter=4)
    texte = st("texte", fontSize=9, leading=13.5, textColor=C(TEXTE_DOUX), spaceAfter=3)
    discret = st("discret", fontSize=7, leading=9.5, textColor=C(DISCRET))

    def p(txt: str, style: ParagraphStyle) -> Paragraph:
        txt = txt.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        return Paragraph(re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", txt), style)

    def tableau(lignes: list[list[str]], largeurs: list[float] | None = None, *, taille: float = 7.5,
                total: bool = True, gauche: int = 1, sous_totaux: bool = False,
                textes: tuple[int, ...] = ()) -> Table:
        num = st("n", fontSize=taille, leading=taille + 2.5, alignment=TA_RIGHT)
        lib = st("l", fontSize=taille, leading=taille + 2.5, textColor=C(TEXTE_DOUX))
        ent = st("e", fontName="Helvetica-Bold", fontSize=taille - 0.5, leading=taille + 2, textColor=C(VIOLET_FONCE))
        entd = st("ed", fontName="Helvetica-Bold", fontSize=taille - 0.5, leading=taille + 2,
                  textColor=C(VIOLET_FONCE), alignment=TA_RIGHT)
        contenu = []
        for i, ligne in enumerate(lignes):
            gras = (total and i == len(lignes) - 1) or (sous_totaux and ligne[0].startswith("Sous-total"))
            row = []
            for j, val in enumerate(ligne):
                a_gauche = j < gauche or j in textes or (j - len(ligne)) in textes
                if i == 0:
                    row.append(p(val, ent if a_gauche else entd))
                else:
                    row.append(p(f"**{val}**" if gras and val else val, lib if a_gauche else num))
            contenu.append(row)
        largeurs = largeurs or [L / len(lignes[0])] * len(lignes[0])
        tab = Table(contenu, colWidths=largeurs, repeatRows=1)
        style = [
            ("BACKGROUND", (0, 0), (-1, 0), C("EDE3F2")),
            ("LINEBELOW", (0, 0), (-1, 0), 0.8, C(VIOLET)),
            ("LINEBELOW", (0, 1), (-1, -1), 0.3, C(TRAIT_LEGER)),
            ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3),
            ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]
        if total:
            style += [("LINEABOVE", (0, -1), (-1, -1), 0.8, C(TEXTE)), ("BACKGROUND", (0, -1), (-1, -1), C("F6F2F8"))]
        if sous_totaux:
            for i, ligne in enumerate(lignes):
                if ligne[0].startswith("Sous-total"):
                    style.append(("BACKGROUND", (0, i), (-1, i), C("F6F2F8")))
        tab.setStyle(TableStyle(style))
        return tab

    # ---- graphiques
    def camembert(valeurs: list[tuple[str, float]]) -> Drawing:
        dessin = Drawing(L, 150)
        donnees = [(lib, v) for lib, v in valeurs if v > 0]
        if not donnees:
            dessin.add(String(0, 70, "Aucune END sur la période", fontSize=8, fillColor=C(DISCRET)))
            return dessin
        total = sum(v for _, v in donnees)
        pie = Pie()
        pie.x, pie.y, pie.width, pie.height = 30, 10, 130, 130
        pie.data = [v for _, v in donnees]
        pie.labels = [f"{100 * v / total:.0f} %" if v / total >= 0.03 else "" for _, v in donnees]
        pie.simpleLabels = 1
        pie.slices.strokeColor = colors.white
        pie.slices.strokeWidth = 1
        pie.slices.fontSize = 7
        pie.slices.fontColor = C(TEXTE)
        pie.slices.labelRadius = 1.18
        for i in range(len(donnees)):
            pie.slices[i].fillColor = C(COULEURS_NATURE[i % len(COULEURS_NATURE)])
        dessin.add(pie)
        leg = Legend()
        leg.x, leg.y = 230, 130
        leg.fontSize, leg.fontName = 7.5, "Helvetica"
        leg.columnMaximum = 8
        leg.dy, leg.deltay = 7, 13
        leg.alignment = "right"
        leg.colorNamePairs = [
            (C(COULEURS_NATURE[i % len(COULEURS_NATURE)]), f"{lib} — {kwh(v)} kWh") for i, (lib, v) in enumerate(donnees)
        ]
        dessin.add(leg)
        return dessin

    def barres_services() -> Drawing:
        dessin = Drawing(L, 175)
        services = [s for s in t.services_end if s[1] > 0]
        if not services:
            return dessin
        bc = VerticalBarChart()
        bc.x, bc.y, bc.width, bc.height = 45, 30, L - 60, 120
        series = [[round(v * 1000) for _, v, _ in services]]
        cibles = any(c for _, _, c in services)
        if cibles:
            series.append([round((c or 0) * 1000) for _, _, c in services])
        bc.data = series
        bc.categoryAxis.categoryNames = [s for s, _, _ in services]
        bc.categoryAxis.labels.fontSize = 6.5
        bc.categoryAxis.labels.angle = 30 if len(services) > 10 else 0
        bc.categoryAxis.labels.dy = -6 if len(services) > 10 else -2
        bc.valueAxis.labels.fontSize = 6.5
        bc.valueAxis.valueMin = 0
        bc.valueAxis.labelTextFormat = lambda v: nb(v)
        bc.valueAxis.gridStrokeColor = C(TRAIT_LEGER)
        bc.valueAxis.visibleGrid = 1
        bc.bars[0].fillColor = C(VIOLET)
        bc.bars.strokeColor = None
        if cibles:
            bc.bars[1].fillColor = C(ORANGE)
        bc.barSpacing, bc.groupSpacing = 1, 6
        dessin.add(bc)
        leg = Legend()
        leg.x, leg.y, leg.fontSize, leg.alignment = 50, 170, 7, "right"
        leg.columnMaximum, leg.dxTextSpace = 1, 4
        leg.colorNamePairs = [(C(VIOLET), "END réalisée (kWh)")] + ([(C(ORANGE), "Cible du service")] if cibles else [])
        dessin.add(leg)
        if not cibles:
            dessin.add(String(L - 10, 170, "Cibles par service : à renseigner", fontSize=6.5,
                              fillColor=C(DISCRET), textAnchor="end"))
        return dessin

    def courbe_cumul() -> Drawing | None:
        if not d.end_par_mois_mwh:
            return None
        cumul, total = [], 0.0
        for v in d.end_par_mois_mwh:
            total += v
            cumul.append(total * 1000)
        dessin = Drawing(L, 165)
        lp = LinePlot()
        lp.x, lp.y, lp.width, lp.height = 55, 25, L - 75, 115
        donnees = [[(i + 1, v) for i, v in enumerate(cumul)]]
        if d.cible_annuelle_mwh:
            mensuelle = d.cible_annuelle_mwh * 1000 / 12
            donnees.append([(m, mensuelle * m) for m in range(1, 13)])
        lp.data = donnees
        lp.lines[0].strokeColor, lp.lines[0].strokeWidth = C(VIOLET), 2
        if d.cible_annuelle_mwh:
            lp.lines[1].strokeColor, lp.lines[1].strokeWidth = C(ORANGE), 1.2
            lp.lines[1].strokeDashArray = [3, 2]
        lp.xValueAxis.valueMin, lp.xValueAxis.valueMax, lp.xValueAxis.valueStep = 1, 12, 1
        lp.xValueAxis.labelTextFormat = lambda m: MOIS[int(m) - 1][:3]
        lp.xValueAxis.labels.fontSize = 6.5
        lp.yValueAxis.valueMin = 0
        lp.yValueAxis.labels.fontSize = 6.5
        lp.yValueAxis.labelTextFormat = lambda v: nb(v)
        lp.yValueAxis.visibleGrid, lp.yValueAxis.gridStrokeColor = 1, C(TRAIT_LEGER)
        dessin.add(lp)
        leg = Legend()
        leg.x, leg.y, leg.fontSize, leg.alignment = 60, 160, 7, "right"
        leg.columnMaximum = 1
        leg.colorNamePairs = [(C(VIOLET), "END cumulée réalisée (kWh)")] + (
            [(C(ORANGE), "Trajectoire de la cible annuelle")] if d.cible_annuelle_mwh else [])
        dessin.add(leg)
        return dessin

    def cartes_indicateurs() -> Table:
        cellules = []
        for i in d.indicateurs:
            couleur = DISCRET if i.atteint is None else (VERT if i.atteint else "C62828")
            u = f" {i.unite}" if i.unite and i.realise is not None else ""
            lignes_c = [
                p(i.libelle.upper(), st("k1", fontName="Helvetica-Bold", fontSize=6.5, leading=8.5, textColor=C(DISCRET))),
                p(f"**{valeur_indicateur(i, i.realise)}**{u}", st("k2", fontSize=15, leading=19, textColor=C(VIOLET_FONCE))),
            ]
            if i.cible is not None:
                lignes_c.append(p(f"Cible {valeur_indicateur(i, i.cible)}", st("k3", fontSize=7, leading=9, textColor=C(couleur))))
            if i.cumul is not None:
                lignes_c.append(p(f"Cumul {valeur_indicateur(i, i.cumul)}"
                                  + (f" / {valeur_indicateur(i, i.cible_cumul)}" if i.cible_cumul else ""),
                                  st("k4", fontSize=7, leading=9, textColor=C(TEXTE_DOUX))))
            cellules.append(lignes_c)
        rangees = [cellules[k:k + 3] for k in range(0, len(cellules), 3)]
        while len(rangees[-1]) < 3:
            rangees[-1].append("")
        tab = Table(rangees, colWidths=[L / 3] * 3)
        tab.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 0.6, C(TRAIT)), ("INNERGRID", (0, 0), (-1, -1), 0.6, C(TRAIT)),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ]))
        return tab

    # ---- pages
    def pied(canvas, doc) -> None:
        canvas.saveState()
        larg, haut = canvas._pagesize
        canvas.setFillColor(C(DISCRET))
        canvas.setFont("Helvetica", 7)
        canvas.drawRightString(larg - 1.5 * cm, haut - 1.1 * cm, REFERENCE)
        canvas.setStrokeColor(C(TRAIT))
        canvas.line(1.5 * cm, 1.3 * cm, larg - 1.5 * cm, 1.3 * cm)
        canvas.drawString(1.5 * cm, 0.9 * cm, f"{TITRE.upper()} — {d.periode.upper()}")
        canvas.drawRightString(larg - 1.5 * cm, 0.9 * cm, f"p. {doc.page}")
        canvas.restoreState()

    def page_carte(canvas, doc) -> None:
        if d.carte and d.carte.services:
            dessiner_carte_end(canvas, d.carte, titre=f"Poids de l'END par service — {d.periode}")
        pied(canvas, doc)

    doc = BaseDocTemplate(str(chemin), pagesize=A4, leftMargin=1.5 * cm, rightMargin=1.5 * cm,
                          topMargin=1.6 * cm, bottomMargin=1.7 * cm, title=f"{TITRE} — {d.periode}",
                          author="SENELEC — Service Conduite des Réseaux")
    portrait = Frame(1.5 * cm, 1.7 * cm, A4[0] - 3 * cm, A4[1] - 3.3 * cm, id="p")
    paysage = Frame(0, 0, landscape(A4)[0], landscape(A4)[1], id="c")
    doc.addPageTemplates([
        PageTemplate(id="portrait", frames=[portrait], onPage=pied, pagesize=A4),
        PageTemplate(id="carte", frames=[paysage], onPage=page_carte, pagesize=landscape(A4)),
    ])

    el: list = []
    entete = [
        p("**Direction Distribution**", st("d1", fontSize=8.5, alignment=TA_RIGHT)),
        p("Département Conduite et Gestion Technique · Service Conduite des Réseaux",
          st("d2", fontSize=7.5, alignment=TA_RIGHT, textColor=C(DISCRET))),
    ]
    logo = Image(str(_LOGO), width=1.9 * cm, height=1.34 * cm) if _LOGO.is_file() else ""
    bandeau = Table([[logo, entete]], colWidths=[3 * cm, L - 3 * cm])
    bandeau.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LINEBELOW", (0, 0), (-1, 0), 0.6, C(TRAIT)),
                                 ("BOTTOMPADDING", (0, 0), (-1, -1), 6), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    el += [bandeau, Spacer(1, 14), p("RAPPORT MENSUEL D'EXPLOITATION · RÉSEAU HTA", sur),
           p(TITRE, h1), p(f"{d.periode.capitalize()} · {' et '.join(d.zones)}", per)]

    el += [p("Indicateurs du mois", h2), cartes_indicateurs(), Spacer(1, 6),
           p("Cibles mensuelles = cible annuelle (Pilotage) au prorata des jours ; cumul : du 1er janvier à la fin du mois.", discret)]
    el += [p("En bref", h2)] + [p(f"• {phrase}", texte) for phrase in d.synthese]

    # I.1
    el += [CondPageBreak(9 * cm), p("I. Exploitation du réseau HTA", h2),
           p("I.1 Incidents — réalisations : nombre d'interruptions et énergie non distribuée", h3)]
    n = len(t.realisations[0])
    el.append(tableau(t.realisations, [5 * cm] + [(L - 5 * cm) / (n - 1)] * (n - 1)))
    if d.cible_mois_mwh:
        el.append(Spacer(1, 4))
        el.append(p(f"Cible {d.periode} (contrat de gestion, au prorata) : **{kwh(d.cible_mois_mwh)} kWh** — "
                    f"réalisé {kwh(d.total.end_mwh)} kWh.", texte))
    el += [KeepTogether([p("Répartition de l'END par nature", h3), camembert(t.natures_end)])]
    el += [KeepTogether([p("END réalisée par service" + (" par rapport à la cible" if d.cibles_service_mwh else ""), h3),
                         barres_services()])]
    cumul = courbe_cumul()
    if cumul:
        el += [KeepTogether([p(f"Suivi de l'END {d.annee} — réalisé cumulé et cible annuelle", h3), cumul])]

    el += [CondPageBreak(6 * cm), p("Récapitulatif des interruptions par service", h3)]
    n = len(t.recap_services[0])
    el.append(tableau(t.recap_services, [3.2 * cm] + [(L - 3.2 * cm) / (n - 1)] * (n - 1), taille=6.8))

    largeurs_evol = [2.6 * cm, 2.2 * cm] + [(L - 4.8 * cm) / 6] * 6
    el += [CondPageBreak(7 * cm), p(f"I.1.2 Évolution par service entre {d.periode_prec} et {d.periode}", h3),
           tableau(t.evolution_m1, largeurs_evol, gauche=2, sous_totaux=True),
           CondPageBreak(7 * cm), p(f"I.1.3 Évolution de l'END par service : {MOIS[d.mois - 1]} {d.annee - 1} et {d.annee}", h3),
           tableau(t.evolution_n1, largeurs_evol, gauche=2, sous_totaux=True)]

    largeurs_top = [4.2 * cm, 3.0 * cm, 1.3 * cm, 1.3 * cm, 1.2 * cm, L - 11 * cm]
    el += [PageBreak(), p("I.1.4 Départs les plus perturbés", h2)]
    for titre, lignes in t.tops:
        el += [KeepTogether([p(titre, h3), tableau(lignes, largeurs_top, total=False, gauche=2, textes=(-1,))])]
    for titre, lignes in t.sieges:
        n = len(lignes[0])
        el += [KeepTogether([p(titre, h3), tableau(lignes, [3 * cm] + [(L - 3 * cm) / (n - 1)] * (n - 1), taille=7)])]
    if t.troncons:
        el += [CondPageBreak(5 * cm), p("I.1.5 Tronçons / antennes fragilisés (3 défauts ou plus dans le mois)", h2)]
        for titre, lignes in t.troncons:
            el += [KeepTogether([p(titre, h3), tableau(lignes, [2.6 * cm, 3.6 * cm, 7.4 * cm, 1.6 * cm, 2.8 * cm],
                                                       total=False, gauche=3, textes=(-1,))])]
    el += [CondPageBreak(5 * cm), p("I.1.6 Le top des tops incidents", h2)]
    for titre, lignes in t.top_des_tops:
        el += [KeepTogether([p(titre, h3), tableau(lignes, largeurs_top, total=False, gauche=2, textes=(-1,))])]

    el += [CondPageBreak(6 * cm), p("I.2 Travaux programmés", h2)]
    el.append(tableau(t.programmes, [6 * cm, 6 * cm, 6 * cm]) if len(t.programmes) > 1
              else p("Aucune coupure pour travaux sur la période.", texte))
    el += [CondPageBreak(7 * cm), p("I.3 Agressions", h2)]
    if t.agressions:
        for titre, lignes in t.agressions:
            el += [KeepTogether([p(titre, h3), tableau(lignes, [5 * cm, 7 * cm, 3 * cm, 3 * cm], gauche=2)])]
    else:
        el.append(p("Aucune agression du réseau enregistrée sur la période.", texte))
    el += [CondPageBreak(6 * cm), p("I.4 Défauts permanents aux 100 km de réseau", h2),
           tableau(t.defauts, [4.5 * cm] * 4, total=False),
           Spacer(1, 6),
           p("Partie basse tension, disponibilité des OMT et indicateurs commerciaux : données hors SIR, "
             "non reprises dans ce rapport.", discret)]

    if d.carte and d.carte.services:
        el += [NextPageTemplate("carte"), PageBreak(), Spacer(1, 1)]
    doc.build(el)


# --------------------------------------------------------------------------------------
# Excel
# --------------------------------------------------------------------------------------


def exporter_xlsx(chemin: Path, d: RapportMensuelData) -> None:
    from openpyxl import Workbook
    from openpyxl.chart import BarChart, LineChart, PieChart, Reference
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    t = construire_tableaux(d)
    wb = Workbook()
    entete_fill = PatternFill("solid", fgColor="EDE3F2")
    total_fill = PatternFill("solid", fgColor="F6F2F8")
    trait = Side(style="thin", color=TRAIT)

    def feuille(titre: str, blocs: list[tuple[str, list[list[str]]]], *, premiere: bool = False):
        ws = wb.active if premiere else wb.create_sheet()
        ws.title = titre[:31]
        ws["A1"] = f"{TITRE} — {d.periode}"
        ws["A1"].font = Font(bold=True, size=13, color=VIOLET_FONCE)
        ws["A2"] = REFERENCE
        ws["A2"].font = Font(size=8, color=DISCRET)
        ligne = 4
        positions = []
        for sous_titre, lignes in blocs:
            ws.cell(row=ligne, column=1, value=sous_titre).font = Font(bold=True, size=10, color=VIOLET)
            ligne += 1
            debut = ligne
            for i, valeurs in enumerate(lignes):
                for j, v in enumerate(valeurs, start=1):
                    num = _vers_nombre(v) if i and j > 1 else None
                    c = ws.cell(row=ligne, column=j, value=num if num is not None else v)
                    c.border = Border(bottom=trait)
                    if i == 0:
                        c.font, c.fill = Font(bold=True, color=VIOLET_FONCE, size=9), entete_fill
                        c.alignment = Alignment(wrap_text=True, vertical="center")
                    elif str(valeurs[0]).startswith(("TOTAL", "Total", "Sous-total")):
                        c.font, c.fill = Font(bold=True), total_fill
                    if num is not None:
                        c.number_format = "#,##0.###" if isinstance(num, float) and not num.is_integer() else "#,##0"
                ligne += 1
            positions.append((debut, ligne - 1, len(lignes[0])))
            ligne += 2
        for col in range(1, 16):
            ws.column_dimensions[get_column_letter(col)].width = 26 if col == 1 else 15
        return ws, positions

    ws, _ = feuille("Synthèse", [("Indicateurs du mois", t.indicateurs)], premiere=True)
    r = ws.max_row + 2
    ws.cell(row=r, column=1, value="En bref").font = Font(bold=True, color=VIOLET)
    for k, phrase in enumerate(d.synthese, start=1):
        ws.cell(row=r + k, column=1, value=phrase.replace("**", ""))
    ws.column_dimensions["F"].width = 60

    ws, pos = feuille("Réalisations", [("Nombre et END par nature", t.realisations)])
    # Camembert de l'END par nature (colonne END total, ou de la seule zone)
    debut, fin, ncol = pos[0]
    pie = PieChart()
    pie.title = "Répartition de l'END par nature"
    col_end = ncol
    pie.add_data(Reference(ws, min_col=col_end, min_row=debut, max_row=fin - 1), titles_from_data=True)
    pie.set_categories(Reference(ws, min_col=1, min_row=debut + 1, max_row=fin - 1))
    pie.height, pie.width = 9, 14
    ws.add_chart(pie, f"A{fin + 3}")

    ws, pos = feuille("Par service", [("Récapitulatif par service", t.recap_services)])
    services = ws.max_row + 3
    ws.cell(row=services, column=1, value="Service").font = Font(bold=True)
    ws.cell(row=services, column=2, value="END (kWh)").font = Font(bold=True)
    ws.cell(row=services, column=3, value="Cible (kWh)").font = Font(bold=True)
    for k, (code, end, cible) in enumerate(t.services_end, start=1):
        ws.cell(row=services + k, column=1, value=code)
        ws.cell(row=services + k, column=2, value=round(end * 1000))
        ws.cell(row=services + k, column=3, value=round(cible * 1000) if cible else None)
    if t.services_end:
        bar = BarChart()
        bar.title = "END réalisée par service (kWh)"
        bar.add_data(Reference(ws, min_col=2, max_col=3, min_row=services, max_row=services + len(t.services_end)),
                     titles_from_data=True)
        bar.set_categories(Reference(ws, min_col=1, min_row=services + 1, max_row=services + len(t.services_end)))
        bar.height, bar.width = 9, 22
        ws.add_chart(bar, f"E{services}")

    feuille("Évolution M-1", [(f"{d.periode_prec} → {d.periode}", t.evolution_m1)])
    feuille("Évolution N-1", [(f"{MOIS[d.mois - 1]} {d.annee - 1} → {d.annee}", t.evolution_n1)])
    feuille("Top départs", t.tops + t.top_des_tops)
    feuille("Sièges permanents", t.sieges)
    if t.troncons:
        feuille("Tronçons fragilisés", t.troncons)
    feuille("Travaux et agressions", [("Travaux programmés", t.programmes)] + t.agressions)
    feuille("Défauts 100 km", [("Défauts permanents aux 100 km", t.defauts)])

    if d.end_par_mois_mwh:
        ws = wb.create_sheet("Cumul END")
        ws.append(["Mois", "END du mois (kWh)", "END cumulée (kWh)", "Cible cumulée (kWh)"])
        cumul = 0.0
        for m, v in enumerate(d.end_par_mois_mwh, start=1):
            cumul += v
            cible = d.cible_annuelle_mwh * 1000 * m / 12 if d.cible_annuelle_mwh else None
            ws.append([MOIS[m - 1], round(v * 1000), round(cumul * 1000), round(cible) if cible else None])
        ligne = LineChart()
        ligne.title = f"Suivi de l'END {d.annee}"
        ligne.add_data(Reference(ws, min_col=3, max_col=4, min_row=1, max_row=len(d.end_par_mois_mwh) + 1),
                       titles_from_data=True)
        ligne.set_categories(Reference(ws, min_col=1, min_row=2, max_row=len(d.end_par_mois_mwh) + 1))
        ligne.height, ligne.width = 9, 18
        ws.add_chart(ligne, "F2")
        for col in "ABCD":
            ws.column_dimensions[col].width = 20
    wb.save(chemin)


def _vers_nombre(v: str):
    """« 1 234 » → 1234, « 12,5 » → 12.5 ; texte sinon (écarts « +5 », pourcentages restent du texte)."""
    if not isinstance(v, str) or not re.fullmatch(r"-?[\d \u00a0]+(,\d+)?", v.strip()):
        return None
    s = v.replace(" ", "").replace("\u00a0", "").replace(",", ".")
    return float(s) if "." in s else int(s)


# --------------------------------------------------------------------------------------
# Word
# --------------------------------------------------------------------------------------


def exporter_docx(chemin: Path, d: RapportMensuelData) -> None:
    from app.utils.docx_simple import Cellule, Docx, Para

    t = construire_tableaux(d)
    doc = Docx()
    L = 17.0

    if _LOGO.is_file():
        doc.image(_LOGO.read_bytes(), 1.9, 1.34)
    doc.grille(
        [[Cellule([Para("Direction Distribution", taille=8, gras=True, couleur=TEXTE, align="right"),
                   Para("Département Conduite et Gestion Technique · Service Conduite des Réseaux", taille=7.5,
                        couleur=DISCRET, align="right", apres=60)], bord_bas=TRAIT)]],
        [L], marge_cm=0.0, espace_apres=120,
    )
    doc.paragraphe(REFERENCE, taille=7, couleur=DISCRET, align="right")
    doc.paragraphe("RAPPORT MENSUEL D'EXPLOITATION · RÉSEAU HTA", gras=True, taille=7.5, couleur=VIOLET, avant=200, apres=40)
    doc.paragraphe(TITRE, gras=True, taille=20, couleur=TEXTE, apres=40)
    doc.paragraphe(f"{d.periode.capitalize()} · {' et '.join(d.zones)}", taille=9, couleur=DISCRET, apres=200)

    def titre(texte: str, niveau: int = 1) -> None:
        doc.paragraphe(texte, gras=True, taille=12 if niveau == 1 else 10,
                       couleur=VIOLET_FONCE if niveau == 1 else TEXTE, avant=240 if niveau == 1 else 160, apres=100)

    def tab(lignes: list[list[str]], **kw) -> None:
        taille = kw.pop("taille", 8)
        doc.tableau(lignes, taille=int(round(taille)), **kw)

    titre("Indicateurs du mois")
    tab(t.indicateurs, largeurs_cm=[4.6, 2.2, 2.2, 2.3, 2.2, 3.5])
    titre("En bref")
    doc.puces(d.synthese)

    titre("I. Exploitation du réseau HTA")
    titre("I.1 Incidents — nombre d'interruptions et énergie non distribuée", 2)
    tab(t.realisations, derniere_ligne_grasse=True, taille=7.5)
    if d.cible_mois_mwh:
        doc.paragraphe(f"Cible {d.periode} (contrat de gestion, au prorata) : **{kwh(d.cible_mois_mwh)} kWh**.", taille=9)
    donnees = [(lib, round(v * 1000)) for lib, v in t.natures_end if v > 0]
    if donnees:
        titre("Répartition de l'END par nature", 2)
        doc.camembert("END par nature (kWh)", [lib for lib, _ in donnees], [v for _, v in donnees])
    titre("Récapitulatif par service", 2)
    tab(t.recap_services, derniere_ligne_grasse=True, taille=6.5)
    titre(f"I.1.2 Évolution par service entre {d.periode_prec} et {d.periode}", 2)
    tab(t.evolution_m1, derniere_ligne_grasse=True, taille=7)
    titre(f"I.1.3 Évolution de l'END par service : {MOIS[d.mois - 1]} {d.annee - 1} et {d.annee}", 2)
    tab(t.evolution_n1, derniere_ligne_grasse=True, taille=7)

    doc.saut_de_page()
    titre("I.1.4 Départs les plus perturbés")
    for sous, lignes in t.tops:
        titre(sous, 2)
        tab(lignes, largeurs_cm=[3.8, 2.8, 1.3, 1.3, 1.2, 6.6], taille=7.5)
    for sous, lignes in t.sieges:
        titre(sous, 2)
        tab(lignes, derniere_ligne_grasse=True, taille=7)
    if t.troncons:
        titre("I.1.5 Tronçons / antennes fragilisés")
        for sous, lignes in t.troncons:
            titre(sous, 2)
            tab(lignes, largeurs_cm=[2.5, 3.3, 6.6, 1.6, 3.0], taille=7.5)
    titre("I.1.6 Le top des tops incidents")
    for sous, lignes in t.top_des_tops:
        titre(sous, 2)
        tab(lignes, largeurs_cm=[3.8, 2.8, 1.3, 1.3, 1.2, 6.6], taille=7.5)
    titre("I.2 Travaux programmés")
    if len(t.programmes) > 1:
        tab(t.programmes, derniere_ligne_grasse=True)
    else:
        doc.paragraphe("Aucune coupure pour travaux sur la période.", taille=9)
    titre("I.3 Agressions")
    if t.agressions:
        for sous, lignes in t.agressions:
            titre(sous, 2)
            tab(lignes, derniere_ligne_grasse=True, taille=7.5)
    else:
        doc.paragraphe("Aucune agression du réseau enregistrée sur la période.", taille=9)
    titre("I.4 Défauts permanents aux 100 km de réseau")
    tab(t.defauts, taille=7.5)
    doc.paragraphe("Partie basse tension, disponibilité des OMT et indicateurs commerciaux : données hors SIR, "
                   "non reprises dans ce rapport.", taille=7, couleur=DISCRET, avant=160)
    doc.enregistrer(chemin)


def exporter_tout(dossier: Path, nom: str, d: RapportMensuelData) -> dict[str, Path]:
    fichiers = {ext: dossier / f"{nom}.{ext}" for ext in ("pdf", "docx", "xlsx")}
    exporter_pdf(fichiers["pdf"], d)
    exporter_docx(fichiers["docx"], d)
    exporter_xlsx(fichiers["xlsx"], d)
    return fichiers


__all__ = ["exporter_tout", "exporter_pdf", "exporter_xlsx", "exporter_docx", "construire_tableaux", "DAKAR", "REGIONS"]
