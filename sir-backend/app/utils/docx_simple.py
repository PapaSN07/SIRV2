"""Générateur .docx minimal (WordprocessingML écrit à la main, sans dépendance).

python-docx n'est pas dans l'image : l'installer demanderait de reconstruire l'image Docker,
ce que le proxy SENELEC empêche (certificat intercepté). Ce module couvre ce dont les rapports
ont besoin : titres, paragraphes avec gras (**texte**), puces, tableaux, image et camembert
(graphique Word natif, valeurs en cache, modifiable dans Word).
"""

from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from xml.sax.saxutils import escape

_EMU_PAR_CM = 360000
_PRIMAIRE = "5B2C6F"  # violet SENELEC
_ENTETE_FOND = "EDE3F2"


def _texte(t: str) -> str:
    return escape(t, {'"': "&quot;"})


def _runs(texte: str, *, taille: int | None = None, couleur: str | None = None, gras: bool = False) -> str:
    """Runs d'un paragraphe ; **…** passe en gras."""
    morceaux = re.split(r"(\*\*[^*]+\*\*)", texte)
    xml = []
    for m in morceaux:
        if not m:
            continue
        b = gras or (m.startswith("**") and m.endswith("**"))
        contenu = m[2:-2] if m.startswith("**") and m.endswith("**") else m
        props = []
        if b:
            props.append("<w:b/>")
        if couleur:
            props.append(f'<w:color w:val="{couleur}"/>')
        if taille:
            props.append(f'<w:sz w:val="{taille * 2}"/><w:szCs w:val="{taille * 2}"/>')
        rpr = f"<w:rPr>{''.join(props)}</w:rPr>" if props else ""
        xml.append(f'<w:r>{rpr}<w:t xml:space="preserve">{_texte(contenu)}</w:t></w:r>')
    return "".join(xml)


@dataclass
class Docx:
    corps: list[str] = field(default_factory=list)
    images: list[tuple[str, bytes]] = field(default_factory=list)
    graphiques: list[str] = field(default_factory=list)

    # ---- blocs ------------------------------------------------------------------------
    def paragraphe(
        self,
        texte: str = "",
        *,
        gras: bool = False,
        taille: int | None = None,
        couleur: str | None = None,
        align: str | None = None,
        apres: int = 120,
        retrait_cm: float = 0.0,
    ) -> None:
        ppr = [f'<w:spacing w:after="{apres}"/>']
        if align:
            ppr.append(f'<w:jc w:val="{align}"/>')
        if retrait_cm:
            ppr.append(f'<w:ind w:left="{int(retrait_cm * 567)}"/>')
        self.corps.append(
            f"<w:p><w:pPr>{''.join(ppr)}</w:pPr>{_runs(texte, taille=taille, couleur=couleur, gras=gras)}</w:p>"
        )

    def titre(self, texte: str, niveau: int = 1) -> None:
        taille = {1: 16, 2: 13, 3: 11}[niveau]
        self.corps.append(
            f'<w:p><w:pPr><w:keepNext/><w:spacing w:before="240" w:after="120"/></w:pPr>'
            f"{_runs(texte, gras=True, taille=taille, couleur=_PRIMAIRE)}</w:p>"
        )

    def puces(self, elements: list[str], *, retrait_cm: float = 0.6) -> None:
        for e in elements:
            self.paragraphe(f"•  {e}", retrait_cm=retrait_cm, apres=60)

    def tableau(
        self,
        lignes: list[list[str]],
        *,
        largeurs_cm: list[float] | None = None,
        entete: bool = True,
        derniere_ligne_grasse: bool = False,
        taille: int = 9,
        premiere_gauche: bool = True,
    ) -> None:
        nb_col = max(len(ligne) for ligne in lignes)
        largeurs = largeurs_cm or [17.0 / nb_col] * nb_col
        grille = "".join(f'<w:gridCol w:w="{int(w * 567)}"/>' for w in largeurs)
        xml = [
            "<w:tbl><w:tblPr><w:tblW w:w=\"0\" w:type=\"auto\"/><w:jc w:val=\"center\"/>"
            "<w:tblBorders>"
            + "".join(
                f'<w:{b} w:val="single" w:sz="4" w:space="0" w:color="BFBFBF"/>'
                for b in ("top", "left", "bottom", "right", "insideH", "insideV")
            )
            + "</w:tblBorders><w:tblCellMar><w:left w:w=\"70\" w:type=\"dxa\"/><w:right w:w=\"70\" w:type=\"dxa\"/>"
            "</w:tblCellMar></w:tblPr>",
            f"<w:tblGrid>{grille}</w:tblGrid>",
        ]
        for i, ligne in enumerate(lignes):
            est_entete = entete and i == 0
            gras = est_entete or (derniere_ligne_grasse and i == len(lignes) - 1)
            xml.append("<w:tr>" + ("<w:trPr><w:tblHeader/></w:trPr>" if est_entete else ""))
            for j in range(nb_col):
                valeur = ligne[j] if j < len(ligne) else ""
                fond = f'<w:shd w:val="clear" w:color="auto" w:fill="{_ENTETE_FOND}"/>' if est_entete else ""
                align = "left" if (j == 0 and premiere_gauche) else "center"
                xml.append(
                    f'<w:tc><w:tcPr><w:tcW w:w="{int(largeurs[j] * 567)}" w:type="dxa"/>{fond}'
                    f'<w:vAlign w:val="center"/></w:tcPr><w:p><w:pPr><w:spacing w:after="0"/>'
                    f'<w:jc w:val="{align}"/></w:pPr>{_runs(valeur, gras=gras, taille=taille)}</w:p></w:tc>'
                )
            xml.append("</w:tr>")
        xml.append("</w:tbl>")
        self.corps.append("".join(xml))
        self.paragraphe("", apres=60)

    def image(self, contenu: bytes, largeur_cm: float, hauteur_cm: float, *, align: str = "left") -> None:
        numero = len(self.images) + 1
        self.images.append((f"image{numero}.png", contenu))
        rid = f"rIdImg{numero}"
        cx, cy = int(largeur_cm * _EMU_PAR_CM), int(hauteur_cm * _EMU_PAR_CM)
        self.corps.append(
            f'<w:p><w:pPr><w:jc w:val="{align}"/></w:pPr><w:r><w:drawing>'
            f'<wp:inline distT="0" distB="0" distL="0" distR="0"><wp:extent cx="{cx}" cy="{cy}"/>'
            f'<wp:docPr id="{100 + numero}" name="Image {numero}"/>'
            '<a:graphic xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
            '<a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">'
            '<pic:pic xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">'
            f'<pic:nvPicPr><pic:cNvPr id="{numero}" name="image{numero}.png"/><pic:cNvPicPr/></pic:nvPicPr>'
            f'<pic:blipFill><a:blip r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
            f'<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>'
            '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr></pic:pic></a:graphicData></a:graphic>'
            "</wp:inline></w:drawing></w:r></w:p>"
        )

    def camembert(
        self, titre: str, categories: list[str], valeurs: list[float], *, largeur_cm: float = 15, hauteur_cm: float = 8
    ) -> None:
        numero = len(self.graphiques) + 1
        pts_cat = "".join(f'<c:pt idx="{i}"><c:v>{_texte(c)}</c:v></c:pt>' for i, c in enumerate(categories))
        pts_val = "".join(f'<c:pt idx="{i}"><c:v>{v:.3f}</c:v></c:pt>' for i, v in enumerate(valeurs))
        couleurs = ("5B2C6F", "E4007C", "F39200", "C0392B", "2E86C1", "16A085", "8E44AD", "D35400",
                    "7F8C8D", "27AE60", "B03A2E", "1F618D")
        dpts = "".join(
            f'<c:dPt><c:idx val="{i}"/><c:bubble3D val="0"/><c:spPr><a:solidFill>'
            f'<a:srgbClr val="{couleurs[i % len(couleurs)]}"/></a:solidFill></c:spPr></c:dPt>'
            for i in range(len(valeurs))
        )
        self.graphiques.append(
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<c:chartSpace xmlns:c="http://schemas.openxmlformats.org/drawingml/2006/chart" '
            'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<c:roundedCorners val="0"/><c:chart>'
            f'<c:title><c:tx><c:rich><a:bodyPr/><a:p><a:pPr><a:defRPr sz="1200" b="1"/></a:pPr>'
            f'<a:r><a:rPr lang="fr-FR" sz="1200" b="1"/><a:t>{_texte(titre)}</a:t></a:r></a:p></c:rich></c:tx>'
            '<c:overlay val="0"/></c:title><c:autoTitleDeleted val="0"/><c:plotArea><c:layout/>'
            '<c:pieChart><c:varyColors val="1"/><c:ser><c:idx val="0"/><c:order val="0"/>'
            f'<c:tx><c:v>{_texte(titre)}</c:v></c:tx>{dpts}'
            '<c:dLbls><c:numFmt formatCode="0%" sourceLinked="0"/><c:spPr><a:noFill/></c:spPr>'
            '<c:txPr><a:bodyPr/><a:p><a:pPr><a:defRPr sz="900" b="1"/></a:pPr><a:endParaRPr lang="fr-FR"/></a:p></c:txPr>'
            '<c:dLblPos val="bestFit"/><c:showLegendKey val="0"/><c:showVal val="0"/><c:showCatName val="1"/>'
            '<c:showSerName val="0"/><c:showPercent val="1"/><c:showBubbleSize val="0"/>'
            '<c:separator>&#10;</c:separator><c:showLeaderLines val="1"/></c:dLbls>'
            f'<c:cat><c:strLit><c:ptCount val="{len(categories)}"/>{pts_cat}</c:strLit></c:cat>'
            f'<c:val><c:numLit><c:formatCode>General</c:formatCode><c:ptCount val="{len(valeurs)}"/>{pts_val}'
            '</c:numLit></c:val></c:ser><c:firstSliceAng val="0"/></c:pieChart></c:plotArea>'
            '<c:legend><c:legendPos val="r"/><c:overlay val="0"/></c:legend><c:plotVisOnly val="1"/>'
            '</c:chart></c:chartSpace>'
        )
        cx, cy = int(largeur_cm * _EMU_PAR_CM), int(hauteur_cm * _EMU_PAR_CM)
        self.corps.append(
            '<w:p><w:pPr><w:jc w:val="center"/></w:pPr><w:r><w:drawing>'
            f'<wp:inline distT="0" distB="0" distL="0" distR="0"><wp:extent cx="{cx}" cy="{cy}"/>'
            f'<wp:docPr id="{200 + numero}" name="Graphique {numero}"/>'
            '<a:graphic xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
            '<a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/chart">'
            '<c:chart xmlns:c="http://schemas.openxmlformats.org/drawingml/2006/chart" '
            f'r:id="rIdChart{numero}"/></a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p>'
        )

    # ---- écriture ---------------------------------------------------------------------
    def enregistrer(self, chemin: Path) -> None:
        document = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
            'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" '
            'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
            'xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">'
            "<w:body>" + "".join(self.corps) + '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
            '<w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1134" w:header="567" w:footer="567" w:gutter="0"/>'
            "</w:sectPr></w:body></w:document>"
        )
        styles = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            '<w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri" w:cs="Calibri" w:eastAsia="Calibri"/>'
            '<w:sz w:val="21"/><w:szCs w:val="21"/><w:lang w:val="fr-FR"/></w:rPr></w:rPrDefault>'
            '<w:pPrDefault><w:pPr><w:spacing w:after="120" w:line="264" w:lineRule="auto"/></w:pPr></w:pPrDefault>'
            "</w:docDefaults>"
            '<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>'
            "</w:styles>"
        )
        rels_doc = ['<Relationship Id="rIdStyles" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>']
        for i, (nom, _) in enumerate(self.images, start=1):
            rels_doc.append(
                f'<Relationship Id="rIdImg{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/{nom}"/>'
            )
        for i in range(1, len(self.graphiques) + 1):
            rels_doc.append(
                f'<Relationship Id="rIdChart{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/chart" Target="charts/chart{i}.xml"/>'
            )
        types = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Default Extension="png" ContentType="image/png"/>'
            '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
            '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
            + "".join(
                f'<Override PartName="/word/charts/chart{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.drawingml.chart+xml"/>'
                for i in range(1, len(self.graphiques) + 1)
            )
            + "</Types>"
        )
        rels = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
            "</Relationships>"
        )
        with zipfile.ZipFile(chemin, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("[Content_Types].xml", types)
            z.writestr("_rels/.rels", rels)
            z.writestr("word/document.xml", document)
            z.writestr("word/styles.xml", styles)
            z.writestr(
                "word/_rels/document.xml.rels",
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                + "".join(rels_doc)
                + "</Relationships>",
            )
            for nom, contenu in self.images:
                z.writestr(f"word/media/{nom}", contenu)
            for i, xml in enumerate(self.graphiques, start=1):
                z.writestr(f"word/charts/chart{i}.xml", xml)
