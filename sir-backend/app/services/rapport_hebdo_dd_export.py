"""Fichiers du rapport hebdomadaire DD : Word et PDF (mise en page validée dans Claude Design le
29/10/2026 : indicateurs clés, répartition, faits marquants, poids des services, cumuls) et Excel
(tableau de bord jour par jour)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from app.services.rapport_hebdo_dd_service import (
    AUTRES_HTA,
    CATEGORIES_HTA,
    CATEGORIES_HTB,
    DAKAR,
    DELESTAGE_HTA,
    FUGITIF,
    JOURS,
    MANOEUVRE_HTA,
    PERMANENT,
    REGIONS,
    SEMI_PERMANENT,
    TRAVAUX_HTA,
    Compte,
    RapportHebdoData,
    ecart_pct,
    fmt_date_longue,
    fmt_mwh,
    fmt_nombre,
    titre_semaine,
)

_LOGO = Path(__file__).resolve().parent.parent / "assets" / "senelec_logo.png"

# Palette (Claude Design) : violet SENELEC, une couleur pour « mieux », une pour « moins bien »
VIOLET, VIOLET_FONCE, VIOLET_MOYEN, LILAS = "5B2C6F", "3E1A4D", "7A4B8C", "B79AC4"
ORANGE, AMBRE, VERT = "F39200", "B86B00", "1E7B34"
TEXTE, TEXTE_DOUX, DISCRET, TRAIT, TRAIT_LEGER, FOND_BARRE = (
    "1F1D24", "34303A", "6B6572", "E8E3EC", "F0EDF3", "F1EEF4",
)
GRIS_CLAIR, GRIS_MOYEN, ZERO = "D9D3DE", "BFB8C5", "C4BFC9"


# --------------------------------------------------------------------------------------
# Vue : tout ce qu'affichent le Word et le PDF, calculé une fois
# --------------------------------------------------------------------------------------

@dataclass
class Indicateur:
    libelle: str
    valeur: str
    unite: str
    ecart: str
    reference: str
    couleur: str


@dataclass
class Segment:
    libelle: str
    nombre: int
    couleur: str


@dataclass
class Barre:
    code: str
    mwh: float
    part: float
    fraction: float
    couleur: str


@dataclass
class Vue:
    surtitre: str
    titre: str
    periode: str
    indicateurs: list[Indicateur]
    en_bref: str
    segments: list[Segment]
    end_detail: list[tuple[str, str]]
    repartition: list[list[str]]
    barres: list[Barre]
    poids: str
    cumul_end: str
    cumul_cible: str
    cumul_depasse: bool | None
    exogenes_mwh: str
    exogenes_nombre: int
    saifi_lignes: list[list[str]]
    pied: str


def fmt_saidi(heures: float) -> str:
    secondes = int(round(heures * 3600))
    h, reste = divmod(secondes, 3600)
    m, s = divmod(reste, 60)
    return f"{h} h {m:02d} min" if h else f"{m} min {s:02d} s"


def _ecart(actuel: float, precedent: float, numero: int) -> tuple[str, str]:
    e = ecart_pct(actuel, precedent)
    if e is None:
        return f"Pas de référence S{numero:02d}", DISCRET
    signe = "+" if e > 0 else "-" if e < 0 else ""
    texte = f"{signe}{fmt_nombre(abs(e), 1)} % vs S{numero:02d}"
    return texte, (AMBRE if e > 0 else VERT if e < 0 else DISCRET)


def tableau_repartition(data: RapportHebdoData) -> list[list[str]]:
    s = data.semaine
    services = data.services
    lignes = [["", *services, "TOTAL"]]
    for cle, libelle in CATEGORIES_HTA:
        valeurs = [s.par_service.get((cle, code), Compte()).nombre for code in services]
        lignes.append([libelle, *[str(v) for v in valeurs], str(sum(valeurs))])
    end = [s.end_service.get(code, 0.0) * 1000 for code in services]
    lignes.append(["**END (kWh)**", *[f"**{fmt_nombre(v)}**" for v in end], f"**{fmt_nombre(sum(end))}**"])
    return lignes


def construire_vue(data: RapportHebdoData) -> Vue:
    s, p = data.semaine, data.precedente
    ts, tp = s.total_hta, p.total_hta
    n = p.numero
    indicateurs = []
    for libelle, va, vp, valeur, unite, ref in (
        ("Interruptions HTA", ts.nombre, tp.nombre, str(ts.nombre), "", f"S{n:02d} : {tp.nombre}"),
        ("END", ts.end_mwh, tp.end_mwh, fmt_nombre(ts.end_mwh, 2), "MWh",
         f"Cible : {fmt_nombre(data.cible_hebdo_mwh)} MWh / semaine" if data.cible_hebdo_mwh
         else f"S{n:02d} : {fmt_nombre(tp.end_mwh, 2)} MWh"),
        ("SAIFI", s.saifi, p.saifi, fmt_nombre(s.saifi, 3), "", f"S{n:02d} : {fmt_nombre(p.saifi, 3)}"),
        ("SAIDI", s.saidi_h, p.saidi_h, fmt_saidi(s.saidi_h), "", f"S{n:02d} : {fmt_saidi(p.saidi_h)}"),
    ):
        texte, couleur = _ecart(float(va), float(vp), n)
        indicateurs.append(Indicateur(libelle, valeur, unite, texte, ref, couleur))

    nb = lambda cle: s.par_categorie.get(cle, Compte()).nombre  # noqa: E731
    segments = [
        Segment("Permanents", nb(PERMANENT), VIOLET_FONCE),
        Segment("Semi-permanents", nb(SEMI_PERMANENT), VIOLET_MOYEN),
        Segment("Fugitifs", nb(FUGITIF), LILAS),
        Segment("Délestages incidents HTA", nb(DELESTAGE_HTA), ORANGE),
        Segment("Travaux HTA", nb(TRAVAUX_HTA), GRIS_CLAIR),
        Segment("Manœuvres et autres", nb(MANOEUVRE_HTA) + nb(AUTRES_HTA), GRIS_MOYEN),
    ]
    end_detail = [
        ("END incidents réseaux", s.somme((PERMANENT, SEMI_PERMANENT, FUGITIF, DELESTAGE_HTA)).end_mwh),
        ("dont facteurs exogènes", s.exogenes.end_mwh),
        ("END travaux HTA", s.par_categorie.get(TRAVAUX_HTA, Compte()).end_mwh),
        ("END autres coupures", s.somme((MANOEUVRE_HTA, AUTRES_HTA)).end_mwh),
    ]

    total_end = sum(s.end_service.values())
    tri = sorted(((c, s.end_service.get(c, 0.0)) for c in data.services), key=lambda kv: kv[1], reverse=True)
    maxi = max((v for _, v in tri), default=0.0)
    barres, cumul, top = [], 0.0, 0
    for i, (code, v) in enumerate(tri):
        part = v * 100 / total_end if total_end else 0.0
        if cumul < 80 and total_end:
            cumul += part
            top = i + 1
        barres.append(Barre(code, v, part, v / maxi if maxi else 0.0, VIOLET if i < top else LILAS))
    poids = f"{top} service(s) font {fmt_nombre(cumul)} % de l'END" if total_end else ""

    cible = data.cible_cumul_mwh
    if cible:
        diff = data.cumul_end_mwh - cible
        depasse = diff > 0
        cumul_cible = (
            f"Cible à date : {fmt_nombre(cible / 1000, 3)} GWh — "
            + (f"dépassée de {fmt_nombre(diff / 1000, 3)} GWh ({'+' if depasse else ''}{fmt_nombre(diff * 100 / cible, 1)} %)"
               if depasse else f"en dessous de {fmt_nombre(-diff / 1000, 3)} GWh")
        )
    else:
        depasse, cumul_cible = None, "Objectif END de l'année non saisi dans Pilotage"

    saifi_lignes = [
        ["Période", "SAIFI", "SAIDI", "Clients impactés", "Clients total"],
        [f"Semaine {s.numero:02d}", fmt_nombre(s.saifi, 3), fmt_saidi(s.saidi_h), fmt_nombre(s.clients_impactes),
         fmt_nombre(s.clients_reference)],
        [f"Semaine {p.numero:02d}", fmt_nombre(p.saifi, 3), fmt_saidi(p.saidi_h), fmt_nombre(p.clients_impactes),
         fmt_nombre(p.clients_reference)],
        [f"Cumul {s.fin.year}", fmt_nombre(data.cumul_saifi, 3), fmt_saidi(data.cumul_saidi_h),
         fmt_nombre(data.cumul_clients_impactes), fmt_nombre(data.cumul_clients_reference)],
    ]
    jours = ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")
    return Vue(
        surtitre="Rapport hebdomadaire d'exploitation · réseau HTA",
        titre=f"Semaine {s.numero:02d} — {s.fin.year}",
        periode=(
            f"Du {jours[s.debut.weekday()]} {fmt_date_longue(s.debut)} au {jours[s.fin.weekday()]} "
            f"{fmt_date_longue(s.fin)} · comparaison avec la semaine {p.numero:02d}"
        ),
        indicateurs=indicateurs,
        en_bref=data.introduction.replace("Il a été noté une ", "").replace("Il a été noté un ", "")[:1].upper()
        + data.introduction.replace("Il a été noté une ", "").replace("Il a été noté un ", "")[1:],
        segments=segments,
        end_detail=[(lib, f"{fmt_mwh(v)} MWh") for lib, v in end_detail],
        repartition=tableau_repartition(data),
        barres=barres,
        poids=poids,
        cumul_end=fmt_nombre(data.cumul_end_mwh / 1000, 3),
        cumul_cible=cumul_cible,
        cumul_depasse=depasse,
        exogenes_mwh=fmt_nombre(data.cumul_end_exogenes_mwh, 1),
        exogenes_nombre=data.cumul_nombre_exogenes,
        saifi_lignes=saifi_lignes,
        pied=f"Généré automatiquement par SIR le {datetime.now():%d/%m/%Y à %Hh%M} · données HTA, tous statuts · "
        "partie BT non incluse",
    )


def _sans_gras(texte: str) -> str:
    return texte.replace("**", "")


# --------------------------------------------------------------------------------------
# Word
# --------------------------------------------------------------------------------------

def exporter_docx(chemin: Path, data: RapportHebdoData) -> None:
    from app.utils.docx_simple import Cellule, Docx, Para

    v = construire_vue(data)
    doc = Docx()
    L = 17.0  # largeur utile (cm)

    def titre_section(texte: str, avant: int = 200) -> None:
        doc.paragraphe(texte, gras=True, taille=11, couleur=TEXTE, avant=avant, apres=100)

    def sous_titre(texte: str) -> Para:
        return Para(texte.upper(), taille=7.5, gras=True, couleur=VIOLET, apres=40)

    # En-tête
    if _LOGO.is_file():
        doc.image(_LOGO.read_bytes(), 1.9, 1.34)
    doc.grille(
        [[Cellule([Para("Direction de la Distribution", taille=8, gras=True, couleur=TEXTE, align="right"),
                   Para("Département Conduite et Gestion Technique · Service Conduite des Réseaux", taille=7.5,
                        couleur=DISCRET, align="right", apres=60)], bord_bas=TRAIT)]],
        [L], marge_cm=0.0, espace_apres=120,
    )
    doc.paragraphe(v.surtitre.upper(), gras=True, taille=7.5, couleur=VIOLET, avant=120, apres=40)
    doc.paragraphe(v.titre, gras=True, taille=24, couleur=TEXTE, apres=40)
    doc.paragraphe(v.periode, taille=9, couleur=DISCRET, apres=200)

    # Indicateurs clés : 4 cartes séparées par un espace
    carte, espace = 4.0, (L - 4 * 4.0) / 3
    cellules: list[Cellule] = []
    for i, k in enumerate(v.indicateurs):
        if i:
            cellules.append(Cellule(""))
        cellules.append(Cellule([
            Para(k.libelle.upper(), taille=7, gras=True, couleur=DISCRET, apres=40),
            Para(f"{k.valeur}{' ' + k.unite if k.unite else ''}", taille=17, gras=True, couleur=TEXTE, apres=40),
            Para(k.ecart, taille=8, gras=True, couleur=k.couleur, apres=20),
            Para(k.reference, taille=7, couleur="8A8490"),
        ], cadre=TRAIT))
    doc.grille([cellules], [carte, espace, carte, espace, carte, espace, carte], marge_cm=0.3, espace_apres=160)

    titre_section("En bref")
    doc.paragraphe(v.en_bref, taille=9.5, couleur=TEXTE_DOUX)

    titre_section("Interruptions de la semaine")
    total = sum(sg.nombre for sg in v.segments) or 1
    largeurs = [max(0.08, L * sg.nombre / total) for sg in v.segments if sg.nombre]
    if largeurs:
        ajust = L / sum(largeurs)
        doc.grille([[Cellule("", fond=sg.couleur) for sg in v.segments if sg.nombre]],
                   [w * ajust for w in largeurs], hauteur_cm=0.32, marge_cm=0.0, espace_apres=100)
    legende: list[list[Cellule]] = []
    for r in range(2):
        ligne: list[Cellule] = []
        for c in range(3):
            sg = v.segments[r * 3 + c]
            ligne += [Cellule("", fond=sg.couleur), Cellule(""),
                      Cellule(sg.libelle, taille=8.5, couleur=TEXTE_DOUX),
                      Cellule(str(sg.nombre), taille=8.5, gras=True, align="right"), Cellule("")]
        legende.append(ligne)
    doc.grille(legende, [0.28, 0.15, 3.9, 0.9, 0.42] * 3, hauteur_cm=0.48, marge_cm=0.0, espace_apres=100)
    doc.grille([[Cellule([Para(lib, taille=7.5, couleur=DISCRET, apres=20), Para(val, taille=11, gras=True)])
                 for lib, val in v.end_detail]], [L / 4] * 4, marge_cm=0.0, espace_apres=160)

    titre_section("Faits marquants")
    gauche = [sous_titre("Faits majeurs")] + [
        Para(f"•  {f}", taille=8.5, couleur=TEXTE_DOUX, apres=50) for f in (data.faits.majeurs or ["Rien à signaler"])
    ]
    droite = [sous_titre("Dakar")] + [
        Para(f"•  {f}", taille=8.5, couleur=TEXTE_DOUX, apres=40) for f in data.faits.dakar
    ] + ([] if data.faits.dakar else [Para("Rien à signaler", taille=8.5, couleur=DISCRET, apres=60)])
    droite += [Para("", apres=60), sous_titre("Régions")] + [
        Para(f"•  {f}", taille=8.5, couleur=TEXTE_DOUX, apres=40) for f in data.faits.regions
    ] + ([] if data.faits.regions else [Para("Rien à signaler", taille=8.5, couleur=DISCRET)])
    doc.grille([[Cellule(gauche), Cellule(""), Cellule(droite)]], [9.0, 0.6, 7.4], marge_cm=0.0)

    # Page 2
    doc.saut_de_page()
    doc.grille([[Cellule(f"Rapport hebdomadaire d'exploitation — S{data.semaine.numero:02d}-{data.semaine.fin.year}",
                         taille=9, gras=True, bord_bas=TRAIT),
                 Cellule("Direction de la Distribution", taille=8, couleur=DISCRET, align="right", bord_bas=TRAIT)]],
               [11.0, 6.0], marge_cm=0.0, espace_apres=120)

    titre_section("Répartition par service de distribution", avant=120)
    rep = v.repartition
    nb_col = len(rep[0])
    larg_svc = (L - 4.3) / max(1, nb_col - 1)
    lignes_rep: list[list[Cellule]] = []
    for i, ligne in enumerate(rep):
        derniere = i == len(rep) - 1
        cells = []
        for j, val in enumerate(ligne):
            texte = _sans_gras(val) if i else ("Catégorie" if j == 0 else ("Total" if j == nb_col - 1 else val))
            zero = i and not derniere and 0 < j < nb_col - 1 and texte == "0"
            cells.append(Cellule(
                "·" if zero else texte,
                taille=8, align="left" if j == 0 else "right",
                gras=(i == 0 and j > 0) or derniere or j == nb_col - 1,
                couleur=ZERO if zero else (DISCRET if i == 0 and j == 0 else TEXTE),
                bord_bas=TEXTE if i == 0 else (None if derniere else TRAIT_LEGER),
                bord_haut=TEXTE if derniere else None,
            ))
        lignes_rep.append(cells)
    doc.grille(lignes_rep, [4.3] + [larg_svc] * (nb_col - 1), marge_cm=0.06, espace_apres=160)

    doc.grille([[Cellule("Poids des services dans l'END", taille=11, gras=True),
                 Cellule(v.poids, taille=8, couleur=DISCRET, align="right")]], [9.0, 8.0], marge_cm=0.0)
    barre_max = 11.6
    for b in v.barres:
        plein = max(0.05, barre_max * b.fraction)
        vide = barre_max - plein
        cells = [Cellule(b.code, taille=8.5, gras=True), Cellule("", fond=b.couleur)]
        largeurs_b = [1.6, plein]
        if vide > 0.02:
            cells.append(Cellule("", fond=FOND_BARRE))
            largeurs_b.append(vide)
        cells += [Cellule(""), Cellule(f"{fmt_nombre(b.mwh, 1)} MWh · {fmt_nombre(b.part)} %", taille=8, align="right")]
        largeurs_b += [0.3, L - 1.6 - barre_max - 0.3]
        doc.grille([cells], largeurs_b, hauteur_cm=0.42, marge_cm=0.0, espace_apres=20)

    doc.paragraphe("", apres=120)
    cartes = [
        Cellule([
            Para(f"END cumulée {data.semaine.fin.year} au {fmt_date_longue(data.semaine.fin)}".upper(), taille=7,
                 gras=True, couleur=DISCRET, apres=40),
            Para(f"{v.cumul_end} GWh", taille=17, gras=True, apres=40),
            Para(v.cumul_cible, taille=8, gras=v.cumul_depasse is not None,
                 couleur=AMBRE if v.cumul_depasse else (VERT if v.cumul_depasse is False else DISCRET)),
        ], cadre=TRAIT),
        Cellule(""),
        Cellule([
            Para(f"Facteurs exogènes {data.semaine.fin.year}".upper(), taille=7, gras=True, couleur=DISCRET, apres=40),
            Para(f"{v.exogenes_mwh} MWh", taille=17, gras=True, apres=40),
            Para(f"{v.exogenes_nombre} interruptions (agressions, chocs accidentels) depuis le 1er janvier", taille=8,
                 couleur=TEXTE_DOUX),
        ], cadre=TRAIT),
    ]
    doc.grille([cartes], [8.3, 0.4, 8.3], marge_cm=0.3, espace_apres=160)

    titre_section("SAIFI et SAIDI")
    lignes_s: list[list[Cellule]] = []
    for i, ligne in enumerate(v.saifi_lignes):
        lignes_s.append([
            Cellule(val, taille=8.5, align="left" if j == 0 else "right",
                    gras=(i == 0 and j > 0) or (i in (1, 3) and j in (1, 2)),
                    couleur=DISCRET if (i == 0 and j == 0) else TEXTE,
                    bord_bas=TEXTE if i == 0 else (TRAIT_LEGER if i < len(v.saifi_lignes) - 1 else None))
            for j, val in enumerate(ligne)
        ])
    doc.grille(lignes_s, [3.4, 2.8, 3.4, 3.8, 3.6], marge_cm=0.06, espace_apres=200)
    doc.paragraphe(v.pied, taille=7.5, couleur="8A8490", avant=200)
    doc.enregistrer(chemin)


# --------------------------------------------------------------------------------------
# PDF
# --------------------------------------------------------------------------------------

def exporter_pdf(chemin: Path, data: RapportHebdoData) -> None:
    import re

    from reportlab.graphics.shapes import Drawing, Rect, String
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_RIGHT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
    )

    v = construire_vue(data)
    C = lambda h: colors.HexColor(f"#{h}")  # noqa: E731
    L = 17.0 * cm - 12  # largeur du cadre (marges internes de 6 pt)

    def st(nom: str, **kw) -> ParagraphStyle:
        base = dict(fontName="Helvetica", fontSize=9, leading=12, textColor=C(TEXTE), spaceAfter=0)
        base.update(kw)
        return ParagraphStyle(nom, **base)

    sur = st("sur", fontName="Helvetica-Bold", fontSize=7.5, textColor=C(VIOLET), spaceAfter=3)
    h1 = st("h1", fontName="Helvetica-Bold", fontSize=24, leading=28, spaceAfter=3)
    per = st("per", fontSize=9, textColor=C(DISCRET), spaceAfter=14)
    h2 = st("h2", fontName="Helvetica-Bold", fontSize=11, leading=14, spaceBefore=12, spaceAfter=6)
    texte = st("texte", fontSize=9.5, leading=14.5, textColor=C(TEXTE_DOUX))
    petit = st("petit", fontSize=8.5, leading=12, textColor=C(TEXTE_DOUX), spaceAfter=3)
    discret = st("discret", fontSize=7.5, leading=10, textColor=C(DISCRET))
    sous = st("sous", fontName="Helvetica-Bold", fontSize=7.5, textColor=C(VIOLET), spaceAfter=4)

    def p(t: str, style: ParagraphStyle) -> Paragraph:
        t = t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        return Paragraph(re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", t), style)

    def pb(markup: str, style: ParagraphStyle) -> Paragraph:
        """Paragraphe dont le balisage (<font>) est écrit ici, texte déjà sûr."""
        return Paragraph(re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", markup.replace("&", "&amp;")), style)

    def carte(contenu: list, largeur: float) -> Table:
        t = Table([[c] for c in contenu], colWidths=[largeur])
        t.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 0.6, C(TRAIT)),
            ("ROUNDEDCORNERS", [6, 6, 6, 6]),
            ("LEFTPADDING", (0, 0), (-1, -1), 9), ("RIGHTPADDING", (0, 0), (-1, -1), 9),
            ("TOPPADDING", (0, 0), (-1, -1), 1.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
            ("TOPPADDING", (0, 0), (-1, 0), 9), ("BOTTOMPADDING", (0, -1), (-1, -1), 9),
        ]))
        return t

    def rangee(cellules: list, largeurs: list[float]) -> Table:
        t = Table([cellules], colWidths=largeurs)
        t.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                               ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                               ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        return t

    def tableau_lignes(
        lignes: list[list[str]], largeurs: list[float], taille: float = 8, repartition: bool = False
    ) -> Table:
        num = st("num", fontSize=taille, leading=taille + 3, alignment=TA_RIGHT)
        lib = st("lib", fontSize=taille, leading=taille + 3, textColor=C(TEXTE_DOUX))
        contenu = []
        for i, ligne in enumerate(lignes):
            rangee_c = []
            for j, val in enumerate(ligne):
                val = _sans_gras(val)
                if repartition and i and 0 < j < len(ligne) - 1 and val == "0" and i < len(lignes) - 1:
                    rangee_c.append(p("·", st("z", fontSize=taille, alignment=TA_RIGHT, textColor=C(ZERO))))
                    continue
                gras = (i == 0 and j > 0) or (repartition and (i == len(lignes) - 1 or j == len(ligne) - 1))
                txt = f"**{val}**" if gras and val else val
                if i == 0:
                    style_c = st("h", fontSize=taille - 0.5, alignment=TA_RIGHT if j else 0,
                                 textColor=C(DISCRET if j == 0 else TEXTE))
                else:
                    style_c = num if j else lib
                rangee_c.append(p(txt, style_c))
            contenu.append(rangee_c)
        t = Table(contenu, colWidths=largeurs)
        style = [("LINEBELOW", (0, 0), (-1, 0), 0.8, C(TEXTE)),
                 ("LINEBELOW", (0, 1), (-1, -2), 0.4, C(TRAIT_LEGER)),
                 ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                 ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                 ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]
        if repartition:
            style.append(("LINEABOVE", (0, -1), (-1, -1), 0.8, C(TEXTE)))
        t.setStyle(TableStyle(style))
        return t

    el: list = []
    # En-tête page 1
    entete_droite = [p("**Direction de la Distribution**", st("ed", fontSize=8, alignment=TA_RIGHT)),
                     p("Département Conduite et Gestion Technique · Service Conduite des Réseaux",
                       st("ed2", fontSize=7.5, alignment=TA_RIGHT, textColor=C(DISCRET)))]
    logo = Image(str(_LOGO), width=1.9 * cm, height=1.34 * cm) if _LOGO.is_file() else Spacer(1, 1)
    en_tete = Table([[logo, entete_droite]], colWidths=[3 * cm, L - 3 * cm])
    en_tete.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LINEBELOW", (0, 0), (-1, 0), 0.6, C(TRAIT)),
                                 ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                                 ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
    el += [en_tete, Spacer(1, 14), p(v.surtitre.upper(), sur), p(v.titre, h1), p(v.periode, per)]

    # Indicateurs clés
    largeur_carte = (L - 3 * 0.32 * cm) / 4
    cartes = []
    for k in v.indicateurs:
        cartes.append(carte([
            p(f"**{k.libelle.upper()}**", st("kl", fontSize=7, textColor=C(DISCRET))),
            pb(f"**{k.valeur}**" + (f" <font size=8 color='#{DISCRET}'>{k.unite}</font>" if k.unite else ""),
              st("kv", fontSize=17, leading=21)),
            p(f"**{k.ecart}**", st("ke", fontSize=8, textColor=C(k.couleur))),
            p(k.reference, st("kr", fontSize=7, textColor=C("8A8490"))),
        ], largeur_carte))
    el.append(rangee([cartes[0], "", cartes[1], "", cartes[2], "", cartes[3]],
                     [largeur_carte, 0.32 * cm] * 3 + [largeur_carte]))

    el += [p("En bref", h2), p(v.en_bref, texte)]

    # Interruptions de la semaine : barre segmentée, légende, END
    el.append(p("Interruptions de la semaine", h2))
    total = sum(sg.nombre for sg in v.segments) or 1
    barre = Drawing(L, 9)
    barre.add(Rect(0, 0, L, 9, rx=4.5, ry=4.5, fillColor=C(FOND_BARRE), strokeColor=None))
    x = 0.0
    for sg in v.segments:
        if not sg.nombre:
            continue
        w = L * sg.nombre / total
        barre.add(Rect(x, 0, w, 9, fillColor=C(sg.couleur), strokeColor=None))
        x += w
    el += [barre, Spacer(1, 7)]
    leg = []
    for r in range(2):
        rang = []
        for c in range(3):
            sg = v.segments[r * 3 + c]
            pastille = Drawing(8, 8)
            pastille.add(Rect(0, 1, 7, 7, rx=1.5, ry=1.5, fillColor=C(sg.couleur), strokeColor=None))
            rang += [pastille, p(sg.libelle, petit), p(f"**{sg.nombre}**", st("ln", fontSize=8.5, alignment=TA_RIGHT)),
                     ""]
        leg.append(rang)
    t_leg = Table(leg, colWidths=[0.42 * cm, 3.9 * cm, 0.9 * cm, 0.45 * cm] * 3)
    t_leg.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                               ("TOPPADDING", (0, 0), (-1, -1), 1), ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
                               ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    el += [t_leg, Spacer(1, 8)]
    el.append(rangee([[p(lib, discret), p(f"**{val}**", st("ev", fontSize=11, leading=14))] for lib, val in v.end_detail],
                     [L / 4] * 4))

    # Faits marquants
    el.append(p("Faits marquants", h2))
    el.append(p("FAITS MAJEURS", sous))
    el += [p(f"•  {f}", petit) for f in (data.faits.majeurs or ["Rien à signaler"])]
    el.append(Spacer(1, 6))
    dakar = [p("DAKAR", sous)] + ([p(f"•  {f}", petit) for f in data.faits.dakar] or [p("Rien à signaler", discret)])
    regions = [p("RÉGIONS", sous)] + (
        [p(f"•  {f}", petit) for f in data.faits.regions] or [p("Rien à signaler", discret)]
    )
    el.append(rangee([dakar, "", regions], [(L - 0.6 * cm) / 2, 0.6 * cm, (L - 0.6 * cm) / 2]))

    # Suite : répartition par service (le texte s'enchaîne, chaque bloc reste entier)
    nb_col = len(v.repartition[0])
    entete_rep = ["Catégorie", *v.repartition[0][1:-1], "Total"]
    el.append(KeepTogether([
        p("Répartition par service de distribution", h2),
        tableau_lignes([entete_rep, *v.repartition[1:]],
                       [3.7 * cm] + [(L - 3.7 * cm) / (nb_col - 1)] * (nb_col - 1), 7.5, repartition=True),
    ]))
    el.append(Spacer(1, 6))

    titre_poids = Table([[p("Poids des services dans l'END", st("h2b", fontName="Helvetica-Bold", fontSize=11)),
                          p(v.poids, st("pd", fontSize=8, alignment=TA_RIGHT, textColor=C(DISCRET)))]],
                        colWidths=[L * 0.55, L * 0.45])
    titre_poids.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                                     ("TOPPADDING", (0, 0), (-1, -1), 12), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                                     ("VALIGN", (0, 0), (-1, -1), "BOTTOM")]))
    hauteur = 15 * len(v.barres)
    graph = Drawing(L, hauteur)
    zone = L - 1.6 * cm - 3.4 * cm
    for i, b in enumerate(v.barres):
        y = hauteur - (i + 1) * 15 + 3
        graph.add(String(0, y + 1, b.code, fontName="Helvetica-Bold", fontSize=8.5, fillColor=C(TEXTE)))
        graph.add(Rect(1.6 * cm, y, zone, 8, rx=4, ry=4, fillColor=C(FOND_BARRE), strokeColor=None))
        graph.add(Rect(1.6 * cm, y, max(2, zone * b.fraction), 8, rx=4, ry=4, fillColor=C(b.couleur), strokeColor=None))
        graph.add(String(L, y + 1, f"{fmt_nombre(b.mwh, 1)} MWh · {fmt_nombre(b.part)} %", fontName="Helvetica",
                         fontSize=8, fillColor=C(TEXTE_DOUX), textAnchor="end"))
    el.append(KeepTogether([titre_poids, graph]))
    el.append(Spacer(1, 14))

    couleur_cible = AMBRE if v.cumul_depasse else (VERT if v.cumul_depasse is False else DISCRET)
    larg = (L - 0.4 * cm) / 2
    fin = data.semaine.fin
    c1 = carte([p(f"**END CUMULÉE {fin.year} AU {fmt_date_longue(fin).upper()}**", st("c1", fontSize=7, textColor=C(DISCRET))),
                pb(f"**{v.cumul_end}** <font size=9 color='#{DISCRET}'>GWh</font>", st("c1v", fontSize=17, leading=22)),
                p(f"**{v.cumul_cible}**" if v.cumul_depasse is not None else v.cumul_cible,
                  st("c1c", fontSize=8, textColor=C(couleur_cible)))], larg)
    c2 = carte([p(f"**FACTEURS EXOGÈNES {fin.year}**", st("c2", fontSize=7, textColor=C(DISCRET))),
                pb(f"**{v.exogenes_mwh}** <font size=9 color='#{DISCRET}'>MWh</font>", st("c2v", fontSize=17, leading=22)),
                p(f"**{v.exogenes_nombre}** interruptions (agressions, chocs accidentels) depuis le 1er janvier",
                  st("c2c", fontSize=8, textColor=C(TEXTE_DOUX)))], larg)
    el.append(rangee([c1, "", c2], [larg, 0.4 * cm, larg]))

    el.append(KeepTogether([p("SAIFI et SAIDI", h2),
                            tableau_lignes(v.saifi_lignes, [3.4 * cm, 2.8 * cm, 3.4 * cm, 3.8 * cm, 3.6 * cm], 8.5)]))

    def pied(canvas, document) -> None:  # noqa: ANN001
        canvas.saveState()
        canvas.setStrokeColor(C(TRAIT))
        canvas.setLineWidth(0.6)
        canvas.line(2 * cm, 1.35 * cm, A4[0] - 2 * cm, 1.35 * cm)
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(C("8A8490"))
        canvas.drawString(2 * cm, 1.0 * cm, v.pied)
        canvas.drawRightString(A4[0] - 2 * cm, 1.0 * cm, f"Page {document.page}")
        if document.page > 1:
            canvas.setFont("Helvetica-Bold", 9)
            canvas.setFillColor(C(TEXTE))
            canvas.drawString(2 * cm, A4[1] - 1.45 * cm,
                              f"Rapport hebdomadaire d'exploitation — S{data.semaine.numero:02d}-{fin.year}")
            canvas.setFont("Helvetica", 8)
            canvas.setFillColor(C(DISCRET))
            canvas.drawRightString(A4[0] - 2 * cm, A4[1] - 1.45 * cm, "Direction de la Distribution")
            canvas.line(2 * cm, A4[1] - 1.65 * cm, A4[0] - 2 * cm, A4[1] - 1.65 * cm)
        canvas.restoreState()

    doc = SimpleDocTemplate(
        str(chemin), pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=2.0 * cm, bottomMargin=1.8 * cm,
        title=f"Rapport hebdomadaire DD {titre_semaine(data)}", author="SIR — SENELEC",
    )
    doc.build(el, onFirstPage=pied, onLaterPages=pied)


# --------------------------------------------------------------------------------------
# Excel — tableau de bord jour par jour
# --------------------------------------------------------------------------------------

def exporter_xlsx(chemin: Path, data: RapportHebdoData) -> None:
    from openpyxl import Workbook
    from openpyxl.chart import PieChart, Reference
    from openpyxl.chart.label import DataLabelList
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    violet = "5B2C6F"
    fond_entete = PatternFill("solid", fgColor="F1EEF4")
    fond_total = PatternFill("solid", fgColor="FAF8FB")
    fin_bord = Side(style="thin", color="BFBFBF")
    bord = Border(left=fin_bord, right=fin_bord, top=fin_bord, bottom=fin_bord)
    gras = Font(bold=True)
    centre = Alignment(horizontal="center", vertical="center", wrap_text=True)
    s = data.semaine
    jours = [s.debut.toordinal() + i for i in range(7)]

    wb = Workbook()
    ws = wb.active
    ws.title = "Synthèse quotidienne"

    def entete_feuille(feuille, titre: str) -> None:
        feuille["A1"] = "Direction de la Distribution"
        feuille["A1"].font = Font(bold=True, color=violet, size=12)
        feuille["A2"] = titre
        feuille["A2"].font = Font(bold=True, size=11)
        feuille["A3"] = f"Semaine {titre_semaine(data)}"

    def cellule(
        feuille, ligne: int, col: int, valeur, *, en_gras: bool = False, fond=None, fmt: str | None = None,
        gauche: bool = False,
    ):
        c = feuille.cell(row=ligne, column=col, value=valeur)
        c.border = bord
        c.alignment = Alignment(vertical="center", wrap_text=True) if (col == 1 or gauche) else centre
        if en_gras:
            c.font = gras
        if fond:
            c.fill = fond
        if fmt:
            c.number_format = fmt
        return c

    entete_feuille(ws, "Tableau de bord de suivi qualité des réseaux de distribution — paramètres du réseau HTA")
    ligne = 5
    cellule(ws, ligne, 1, "Zone", en_gras=True, fond=fond_entete)
    cellule(ws, ligne, 2, "Paramètres", en_gras=True, fond=fond_entete)
    ws.merge_cells(start_row=ligne, start_column=3, end_row=ligne, end_column=10)
    cellule(ws, ligne, 3, "Nombre", en_gras=True, fond=fond_entete)
    ws.merge_cells(start_row=ligne, start_column=11, end_row=ligne, end_column=18)
    cellule(ws, ligne, 11, "END (kWh)", en_gras=True, fond=fond_entete)
    ligne += 1
    cellule(ws, ligne, 1, "", fond=fond_entete)
    cellule(ws, ligne, 2, "", fond=fond_entete)
    for bloc in (3, 11):
        for i, j in enumerate(jours):
            jour = date.fromordinal(j)
            cellule(ws, ligne, bloc + i, f"{JOURS[i][:3]}. {jour:%d/%m}", en_gras=True, fond=fond_entete)
        cellule(ws, ligne, bloc + 7, "Cumul semaine", en_gras=True, fond=fond_entete)
    ligne += 1

    categories = [*CATEGORIES_HTA, ("exogenes", "dont facteurs exogènes (choc accidentel…)"), *CATEGORIES_HTB]
    for z in (DAKAR, REGIONS, None):
        debut_bloc = ligne
        for cle, libelle in categories:
            cellule(ws, ligne, 1, z or "TOTAL", en_gras=True)
            cellule(ws, ligne, 2, libelle, en_gras=cle == "exogenes", gauche=True)
            for i in range(7):
                if cle == "exogenes":
                    comptes = [s.exogenes_jour.get((i, zz), Compte()) for zz in ((z,) if z else (DAKAR, REGIONS))]
                else:
                    comptes = [s.par_jour.get((i, cle, zz), Compte()) for zz in ((z,) if z else (DAKAR, REGIONS))]
                cellule(ws, ligne, 3 + i, sum(c.nombre for c in comptes))
                cellule(ws, ligne, 11 + i, round(sum(c.end_mwh for c in comptes) * 1000), fmt="# ##0")
            cellule(ws, ligne, 10, f"=SUM({get_column_letter(3)}{ligne}:{get_column_letter(9)}{ligne})", en_gras=True)
            cellule(ws, ligne, 18, f"=SUM({get_column_letter(11)}{ligne}:{get_column_letter(17)}{ligne})",
                    en_gras=True, fmt="# ##0")
            ligne += 1
        ws.merge_cells(start_row=debut_bloc, start_column=1, end_row=ligne - 1, end_column=1)
        nb_hta = len(CATEGORIES_HTA)
        cellule(ws, ligne, 1, f"Total HTA {z or 'national'}", en_gras=True, fond=fond_total)
        cellule(ws, ligne, 2, "Toutes interruptions HTA", en_gras=True, fond=fond_total, gauche=True)
        for col in list(range(3, 11)) + list(range(11, 19)):
            lettre = get_column_letter(col)
            cellule(ws, ligne, col, f"=SUM({lettre}{debut_bloc}:{lettre}{debut_bloc + nb_hta - 1})", en_gras=True,
                    fond=fond_total, fmt="# ##0" if col >= 11 else None)
        ligne += 2

    ws.column_dimensions["A"].width = 14
    ws.column_dimensions["B"].width = 44
    for col in range(3, 19):
        ws.column_dimensions[get_column_letter(col)].width = 10.5
    ws.freeze_panes = "C7"

    # ---- Répartition par service --------------------------------------------------------
    wr = wb.create_sheet("Répartition par SD")
    entete_feuille(wr, "Répartition des interruptions par service de distribution")
    services = data.services
    ligne = 5
    blocs: list[tuple[str, int | None]] = [(f"{JOURS[i]} {date.fromordinal(jours[i]):%d/%m/%Y}", i) for i in range(7)]
    blocs.append((f"Semaine S{s.numero:02d}", None))
    ligne_end_semaine = 0
    for titre_bloc, jour in blocs:
        cellule(wr, ligne, 1, titre_bloc, en_gras=True, fond=fond_entete)
        for j, code in enumerate(services):
            cellule(wr, ligne, 2 + j, code, en_gras=True, fond=fond_entete)
        cellule(wr, ligne, 2 + len(services), "TOTAL", en_gras=True, fond=fond_entete)
        ligne += 1
        for cle, libelle in CATEGORIES_HTA:
            cellule(wr, ligne, 1, libelle)
            for j, code in enumerate(services):
                c = s.par_service.get((cle, code), Compte()) if jour is None else s.par_jour_service.get((jour, cle, code), Compte())
                cellule(wr, ligne, 2 + j, c.nombre)
            fin_col = get_column_letter(1 + len(services))
            cellule(wr, ligne, 2 + len(services), f"=SUM(B{ligne}:{fin_col}{ligne})", en_gras=True)
            ligne += 1
        cellule(wr, ligne, 1, "END (kWh)", en_gras=True, fond=fond_total)
        for j, code in enumerate(services):
            if jour is None:
                valeur = s.end_service.get(code, 0.0)
            else:
                valeur = sum(s.par_jour_service.get((jour, cle, code), Compte()).end_mwh for cle, _ in CATEGORIES_HTA)
            cellule(wr, ligne, 2 + j, round(valeur * 1000), en_gras=True, fond=fond_total, fmt="# ##0")
        fin_col = get_column_letter(1 + len(services))
        cellule(wr, ligne, 2 + len(services), f"=SUM(B{ligne}:{fin_col}{ligne})", en_gras=True, fond=fond_total,
                fmt="# ##0")
        if jour is None:
            ligne_end_semaine = ligne
        ligne += 2
    wr.column_dimensions["A"].width = 40
    for j in range(len(services) + 1):
        wr.column_dimensions[get_column_letter(2 + j)].width = 10
    if services and ligne_end_semaine:
        camembert = PieChart()
        camembert.title = f"END par service — S{s.numero:02d}"
        valeurs = Reference(wr, min_col=2, max_col=1 + len(services), min_row=ligne_end_semaine)
        libelles = Reference(wr, min_col=2, max_col=1 + len(services), min_row=ligne_end_semaine - len(CATEGORIES_HTA) - 1)
        camembert.add_data(valeurs, from_rows=True, titles_from_data=False)
        camembert.set_categories(libelles)
        camembert.dataLabels = DataLabelList()
        camembert.dataLabels.showPercent = True
        camembert.dataLabels.showVal = False
        camembert.dataLabels.showCatName = False
        camembert.dataLabels.showSerName = False
        camembert.dataLabels.showLegendKey = False
        camembert.height, camembert.width = 9, 14
        wr.add_chart(camembert, f"{get_column_letter(len(services) + 4)}5")

    # ---- Synthèse (mêmes chiffres que le Word) -----------------------------------------
    wsy = wb.create_sheet("Synthèse semaine")
    entete_feuille(wsy, "Synthèse de la semaine")
    lignes_synthese = [
        ("Interruptions HTA (semaine)", s.total_hta.nombre),
        ("END HTA semaine (MWh)", round(s.total_hta.end_mwh, 3)),
        ("dont facteurs exogènes (MWh)", round(s.exogenes.end_mwh, 3)),
        ("SAIFI semaine", round(s.saifi, 4)),
        ("SAIDI semaine (h)", round(s.saidi_h, 4)),
        ("Clients impactés (semaine)", s.clients_impactes),
        ("Nombre total de clients", s.clients_reference),
        (f"Cumul END {s.fin.year} (MWh)", round(data.cumul_end_mwh, 3)),
        ("Valeur cible cumulée (MWh)", round(data.cible_cumul_mwh, 3) if data.cible_cumul_mwh else "Objectif non saisi"),
        (f"Cumul END exogènes {s.fin.year} (MWh)", round(data.cumul_end_exogenes_mwh, 3)),
        ("Cumul interruptions exogènes", data.cumul_nombre_exogenes),
        (f"SAIFI cumul {s.fin.year}", round(data.cumul_saifi, 4)),
        (f"SAIDI cumul {s.fin.year} (h)", round(data.cumul_saidi_h, 4)),
    ]
    for i, (libelle, valeur) in enumerate(lignes_synthese, start=5):
        cellule(wsy, i, 1, libelle, en_gras=True)
        cellule(wsy, i, 2, valeur)
    base = 5 + len(lignes_synthese) + 1
    wsy.cell(row=base, column=1, value="Faits marquants").font = Font(bold=True, color=violet)
    r = base + 1
    for titre_section, faits in (("Faits majeurs", data.faits.majeurs), ("Dakar", data.faits.dakar), ("Régions", data.faits.regions)):
        wsy.cell(row=r, column=1, value=titre_section).font = gras
        r += 1
        for f in faits or ["RAS"]:
            wsy.cell(row=r, column=1, value=f"• {f}")
            r += 1
    wsy.column_dimensions["A"].width = 46
    wsy.column_dimensions["B"].width = 18

    for feuille in (ws, wr, wsy):
        feuille.page_setup.orientation = "landscape"
        feuille.page_setup.paperSize = feuille.PAPERSIZE_A4
        feuille.page_setup.fitToWidth = 1
        feuille.page_setup.fitToHeight = 0
        feuille.sheet_properties.pageSetUpPr.fitToPage = True
    wb.save(chemin)


def exporter_tout(dossier: Path, nom_base: str, data: RapportHebdoData) -> dict[str, Path]:
    """Écrit les trois fichiers ; renvoie {extension: chemin}."""
    chemins = {ext: dossier / f"{nom_base}.{ext}" for ext in ("docx", "xlsx", "pdf")}
    exporter_docx(chemins["docx"], data)
    exporter_xlsx(chemins["xlsx"], data)
    exporter_pdf(chemins["pdf"], data)
    return chemins
