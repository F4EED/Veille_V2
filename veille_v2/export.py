"""Rapports PDF, HTML et Markdown, déposés sur les Pages Perso."""

from __future__ import annotations

import ftplib
import json
import os
import re
import threading
import unicodedata
from datetime import datetime
from html import escape
from io import BytesIO
from pathlib import Path
from typing import Any

import yaml

from veille_v2 import filtre, magasin
from veille_v2.texte import sans_accents

V1 = Path(r"C:\Apps\veille_techno\config")
DATA = Path(__file__).resolve().parent.parent / "data"
MANIFESTE = DATA / "publications.json"
DOSSIER = "Veille_2"
URL_BASE = "https://f4eed.pages-perso.free.fr"

NOMS = {
    "iot": "Veille_IOT",
    "crise": "Veille_Crise",
    "radio": "Veille_Radio",
    "outils": "Veille_Outils_PC",
    "blackout": "Veille_Blackout",
    "geomatique": "Veille_Geomatique",
    "mesh": "Veille_Mesh",
}


def _charger(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _identifiants() -> dict[str, str]:
    cfg = _charger(V1 / "email.yaml")
    secrets = _charger(V1 / "email.secrets.yaml")
    pub = dict(cfg.get("publication") or {})
    smtp = dict(cfg.get("smtp") or {})
    utilisateur = str(pub.get("utilisateur") or smtp.get("utilisateur") or cfg.get("expediteur") or "")
    utilisateur = utilisateur.split("@", 1)[0]
    return {
        "hote": str(pub.get("hote") or "ftpperso.free.fr"),
        "utilisateur": utilisateur,
        "mot_de_passe": str(secrets.get("mot_de_passe") or ""),
    }


def nom_base(profil_id: str, titre: str) -> str:
    if profil_id in NOMS:
        return NOMS[profil_id]
    brut = re.sub(r"[^A-Za-z0-9]+", "_", sans_accents(titre)).strip("_") or "Veille"
    if not brut.lower().startswith("veille"):
        brut = "Veille_" + brut
    return brut[:60]


MOIS = (
    "janvier",
    "février",
    "mars",
    "avril",
    "mai",
    "juin",
    "juillet",
    "août",
    "septembre",
    "octobre",
    "novembre",
    "décembre",
)


def _date_courte(iso: str | None) -> str:
    if not iso or len(iso) < 10:
        return ""
    return f"{iso[8:10]}/{iso[5:7]}/{iso[0:4]}"


def _date_longue(iso: str | None) -> str:
    if not iso or len(iso) < 10:
        return ""
    try:
        mois = MOIS[int(iso[5:7]) - 1]
    except (ValueError, IndexError):
        return _date_courte(iso)
    return f"{int(iso[8:10])} {mois} {iso[0:4]}"


def _propre(texte: str) -> str:
    texte = re.sub(r"[\U00010000-\U0010ffff]", "", texte or "")
    texte = texte.replace("\u2011", "-").replace("\u2010", "-").replace("\u00a0", " ").replace("\u202f", " ")
    return re.sub(r"\s+", " ", texte).strip()


def _pdf_texte(texte: str) -> str:
    """Garde lettres, chiffres et ponctuation que Georgia et Calibri dessinent vraiment."""
    gardes = set("–—‘’“”…«»•·€")
    morceaux: list[str] = []
    for caractere in _propre(texte):
        if caractere in gardes:
            morceaux.append(caractere)
            continue
        famille = unicodedata.category(caractere)
        if famille.startswith(("L", "N", "P")) or famille == "Zs":
            morceaux.append(caractere)
    return "".join(morceaux)


def _ancre(label: str) -> str:
    base = sans_accents(label).lower()
    return re.sub(r"[^a-z0-9]+", "-", base).strip("-") or "rubrique"


def _resume(article: dict[str, Any], taille: int = 420) -> str:
    texte = _propre(article.get("resume") or "")
    if len(texte) <= taille:
        return texte
    coupe = texte[:taille].rsplit(" ", 1)[0]
    return coupe + "…"


def _groupes(data: dict[str, Any]) -> list[tuple[str, list[dict[str, Any]]]]:
    seaux: dict[str, list[dict[str, Any]]] = {}
    ordre: list[str] = []
    for rubrique in data.get("rubriques") or []:
        if rubrique.get("nombre"):
            label = rubrique["label"]
            ordre.append(label)
            seaux[label] = []
    for article in data.get("articles") or []:
        label = article.get("domaine_label") or "Sans rubrique"
        if label not in seaux:
            ordre.append(label)
            seaux[label] = []
        seaux[label].append(article)
    return [(label, seaux[label]) for label in ordre if seaux[label]]


def _contenu(profil_id: str, jours: int) -> tuple[dict[str, Any], dict[str, Any], list[tuple[str, list[dict[str, Any]]]]]:
    fiche = magasin.profil(profil_id)
    if fiche is None:
        raise ValueError("Veille introuvable.")
    data = filtre.lister(profil_id, jours, limite=800, resume_max=900)
    return fiche, data, _groupes(data)


def rendre_markdown(profil_id: str, jours: int) -> str:
    fiche, data, groupes = _contenu(profil_id, jours)
    maintenant = datetime.now()
    quand = f"{maintenant.day} {MOIS[maintenant.month - 1]} {maintenant.year}, {maintenant.strftime('%H:%M')}"
    total = data.get("total", 0)
    lignes = [
        f"# {fiche['titre']}",
        "",
        f"> {_propre(fiche.get('perimetre') or 'Veille')}",
        "",
        f"- **Articles** — {total}",
        f"- **Fenêtre** — {jours} jours",
        f"- **Export** — {quand}",
        "",
    ]
    if not groupes:
        lignes.extend(["Aucun article dans cette fenêtre.", ""])
        return "\n".join(lignes)
    lignes.append("## Sommaire")
    lignes.append("")
    for label, articles in groupes:
        lignes.append(f"- [{label}](#{_ancre(label)}) — {len(articles)}")
    lignes.append("")
    for label, articles in groupes:
        lignes.extend(
            [
                "---",
                "",
                f"## {label}",
                "",
                f"*{len(articles)} article{'s' if len(articles) > 1 else ''}*",
                "",
            ]
        )
        for article in articles:
            titre = _propre(article.get("titre") or "Sans titre").replace("[", "\\[").replace("]", "\\]")
            lignes.append(f"### {titre}")
            lignes.append("")
            meta = []
            if article.get("source"):
                meta.append(f"**{_propre(article['source'])}**")
            date = _date_longue(article.get("date"))
            if date:
                meta.append(date)
            if meta:
                lignes.append(" · ".join(meta))
                lignes.append("")
            mots = [_propre(mot) for mot in (article.get("mots") or [])[:5] if _propre(mot)]
            if mots:
                lignes.append(" ".join(f"`{mot}`" for mot in mots))
                lignes.append("")
            resume = _resume(article)
            if resume:
                lignes.append(f"> {resume}")
                lignes.append("")
            if article.get("lien"):
                lignes.append(f"[Lire l'article]({article['lien']})")
                lignes.append("")
    return "\n".join(lignes).rstrip() + "\n"


def rendre_html(profil_id: str, jours: int) -> str:
    fiche, data, groupes = _contenu(profil_id, jours)
    maintenant = datetime.now().strftime("%d/%m/%Y à %H:%M")
    sections: list[str] = []
    if not groupes:
        sections.append("<p>Aucun article dans cette fenêtre.</p>")
    for label, articles in groupes:
        fiches = []
        for article in articles:
            titre = escape(article.get("titre") or "Sans titre")
            lien = article.get("lien") or ""
            titre_html = f'<a href="{escape(lien)}">{titre}</a>' if lien else titre
            meta = " · ".join(
                escape(part)
                for part in (article.get("source") or "", _date_courte(article.get("date")))
                if part
            )
            mots = "".join(f"<span>{escape(mot)}</span>" for mot in (article.get("mots") or [])[:6])
            resume = f"<p>{escape(article['resume'])}</p>" if article.get("resume") else ""
            fiches.append(
                f"<article><h3>{titre_html}</h3><p class='meta'>{meta}</p><p class='mots'>{mots}</p>{resume}</article>"
            )
        sections.append(f"<section><h2>{escape(label)}</h2>{''.join(fiches)}</section>")
    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(fiche['titre'])}</title>
<style>
*, *::before, *::after {{ box-sizing: border-box; }}
body {{ margin: 0; font: 1rem/1.45 "Segoe UI", sans-serif; background: #f4f1ea; color: #1c1917; overflow-wrap: anywhere; }}
header {{ background: #1c1917; color: #fff; padding: max(1.25rem, env(safe-area-inset-top)) 1rem 1.15rem max(1rem, env(safe-area-inset-left)); }}
h1 {{ margin: 0; font-size: clamp(1.45rem, 6vw, 2rem); }}
header p, header a {{ color: #fff; }}
header a {{ display: inline-block; padding: .45rem 0; }}
main {{ max-width: 42rem; margin: 0 auto; padding: 1rem 1rem 2rem; }}
section {{ background: #fff; border-radius: 14px; padding: 1rem; margin: 0 0 1rem; box-shadow: 0 6px 18px rgba(0,0,0,.06); }}
h2 {{ margin: 0 0 .6rem; font-size: 1.15rem; }}
article {{ padding: .75rem 0; border-top: 1px solid #e7e5e4; }}
h3 {{ margin: 0; font-size: 1.05rem; line-height: 1.3; }}
a {{ color: #0f4c5c; }}
.meta {{ margin: .25rem 0; color: #57534e; font-size: .9rem; }}
.mots span {{ display: inline-block; margin: .15rem .3rem 0 0; background: #eef2e4; border-radius: 999px; padding: .1rem .45rem; font-size: .75rem; }}
article p {{ margin: .35rem 0 0; }}
</style>
</head>
<body>
<header>
<p><a href="index.html">Veille 2</a></p>
<h1>{escape(fiche['titre'])}</h1>
<p>{escape(fiche.get('perimetre') or '')}</p>
<p>{data.get('total', 0)} article(s) · {jours} jours · {escape(maintenant)}</p>
</header>
<main>
{''.join(sections)}
</main>
</body>
</html>
"""


def rendre_pdf(profil_id: str, jours: int) -> bytes:
    from fpdf import FPDF

    encre = (28, 26, 23)
    marine = (27, 54, 72)
    cuivre = (158, 116, 62)
    muet = (110, 102, 94)
    papier = (246, 243, 237)
    carte = (255, 253, 250)
    ombre = (226, 219, 208)
    puce = (232, 236, 234)

    fiche, data, groupes = _contenu(profil_id, jours)
    windir = Path(os.environ.get("WINDIR") or r"C:\Windows") / "Fonts"
    titre_r = windir / "georgia.ttf"
    titre_b = windir / "georgiab.ttf"
    titre_i = windir / "georgiai.ttf"
    corps_r = windir / "calibri.ttf"
    corps_b = windir / "calibrib.ttf"
    if not titre_r.is_file() or not corps_r.is_file():
        raise FileNotFoundError("Polices Georgia ou Calibri introuvables pour le PDF.")

    class Rapport(FPDF):
        nom_veille = _pdf_texte(fiche["titre"])

        def header(self) -> None:
            self.set_fill_color(*marine)
            self.rect(0, 0, 5.2, self.h, "F")
            self.set_fill_color(*cuivre)
            self.rect(5.2, 0, 0.7, self.h, "F")
            if self.page_no() == 1:
                return
            self.set_xy(self.l_margin, 8)
            self.set_font("Titre", "I" if titre_i.is_file() else "", 8.5)
            self.set_text_color(*marine)
            nom = self.nom_veille if len(self.nom_veille) <= 52 else self.nom_veille[:50].rsplit(" ", 1)[0] + "…"
            self.cell(self.epw * 0.72, 5, nom)
            self.set_font("Corps", "", 8)
            self.set_text_color(*muet)
            self.cell(self.epw * 0.28, 5, "Veille vive", align="R")
            self.set_draw_color(*cuivre)
            self.set_line_width(0.3)
            self.line(self.l_margin, 14.2, self.w - self.r_margin, 14.2)
            self.set_y(18)

        def footer(self) -> None:
            self.set_y(-12)
            self.set_font("Corps", "", 8)
            self.set_text_color(148, 140, 130)
            label = str(self.page_no())
            large = self.get_string_width(label)
            centre = self.w / 2
            y = self.get_y() + 2.4
            self.set_draw_color(206, 198, 186)
            self.set_line_width(0.2)
            self.line(self.l_margin, y, centre - large / 2 - 3, y)
            self.line(centre + large / 2 + 3, y, self.w - self.r_margin, y)
            self.set_xy(centre - large / 2, self.get_y())
            self.cell(large, 5, label, align="C")

    pdf = Rapport()
    pdf.set_page_background(papier)
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.set_margins(16, 16, 15)
    pdf.add_font("Titre", "", str(titre_r))
    pdf.add_font("Titre", "B", str(titre_b if titre_b.is_file() else titre_r))
    if titre_i.is_file():
        pdf.add_font("Titre", "I", str(titre_i))
    pdf.add_font("Corps", "", str(corps_r))
    pdf.add_font("Corps", "B", str(corps_b if corps_b.is_file() else corps_r))
    pdf.add_page()
    largeur = pdf.epw
    inner_w = largeur - 8.4

    def mesure(famille: str, style: str, taille: float, interligne: float, texte: str, zone: float) -> float:
        if not texte:
            return 0.0
        x, y = pdf.x, pdf.y
        pdf.set_font(famille, style, taille)
        hauteur = pdf.multi_cell(zone, interligne, texte, align="L", dry_run=True, output="HEIGHT")
        pdf.set_xy(x, y)
        return float(hauteur)

    def ecrire(famille: str, style: str, taille: float, interligne: float, texte: str, couleur: tuple[int, int, int], x: float, zone: float) -> None:
        pdf.set_x(x)
        pdf.set_text_color(*couleur)
        pdf.set_font(famille, style, taille)
        pdf.multi_cell(zone, interligne, texte, align="L")

    def lignes_mots(mots: list[str], zone: float) -> list[list[str]]:
        pdf.set_font("Corps", "B", 7.5)
        lignes: list[list[str]] = []
        ligne: list[str] = []
        occupe = 0.0
        for mot in mots:
            large = pdf.get_string_width(mot) + 3.8
            if ligne and occupe + large > zone:
                lignes.append(ligne)
                ligne = [mot]
                occupe = large + 1.3
            else:
                ligne.append(mot)
                occupe += large + 1.3
        if ligne:
            lignes.append(ligne)
        return lignes

    def dessiner_mots(mots: list[str], x: float, y: float, zone: float) -> float:
        pdf.set_font("Corps", "B", 7.5)
        curseur_x = x
        curseur_y = y
        for mot in mots:
            large = pdf.get_string_width(mot) + 3.8
            if curseur_x + large > x + zone and curseur_x > x:
                curseur_x = x
                curseur_y += 5.8
            pdf.set_fill_color(*puce)
            pdf.rect(curseur_x, curseur_y, large, 4.6, "F")
            pdf.set_xy(curseur_x + 1.9, curseur_y + 0.7)
            pdf.set_text_color(*marine)
            pdf.cell(large - 3.8, 3.3, mot)
            curseur_x += large + 1.3
        return curseur_y + 4.6

    maintenant = datetime.now()
    quand = f"{maintenant.day} {MOIS[maintenant.month - 1]} {maintenant.year}"
    y = pdf.get_y()
    pdf.set_char_spacing(1.15)
    pdf.set_xy(pdf.l_margin, y)
    pdf.set_font("Titre", "", 8)
    pdf.set_text_color(*marine)
    pdf.cell(pdf.get_string_width("VEILLE VIVE") + 4, 5, "VEILLE VIVE")
    pdf.set_char_spacing(0)
    pdf.set_xy(pdf.l_margin, y)
    pdf.set_font("Corps", "", 9.5)
    pdf.set_text_color(*muet)
    pdf.cell(largeur, 5, quand, align="R")
    pdf.ln(7)
    pdf.set_draw_color(*marine)
    pdf.set_line_width(0.25)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
    pdf.ln(5)

    titre = _pdf_texte(fiche["titre"]) or "Veille"
    ecrire("Titre", "B", 24, 10.2, titre, encre, pdf.l_margin, largeur)
    pdf.ln(1.2)
    perimetre = _pdf_texte(fiche.get("perimetre") or "")
    if len(perimetre) > 220:
        perimetre = perimetre[:217].rsplit(" ", 1)[0] + "…"
    if perimetre:
        ecrire("Corps", "", 11, 5.2, perimetre, muet, pdf.l_margin, largeur)
    pdf.ln(2.2)
    pdf.set_draw_color(*cuivre)
    pdf.set_line_width(0.7)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.l_margin + 28, pdf.get_y())
    pdf.ln(5.5)

    total = int(data.get("total") or 0)
    indicateurs = (
        (str(total), "article" if total <= 1 else "articles"),
        (str(jours), "jour" if jours <= 1 else "jours"),
        (str(len(groupes)), "rubrique" if len(groupes) <= 1 else "rubriques"),
    )
    boite_w = (largeur - 6) / 3
    boite_h = 16
    y_boites = pdf.get_y()
    for index, (nombre, legend) in enumerate(indicateurs):
        x = pdf.l_margin + index * (boite_w + 3)
        pdf.set_fill_color(*carte)
        pdf.rect(x, y_boites, boite_w, boite_h, "F")
        pdf.set_fill_color(*marine)
        pdf.rect(x, y_boites, boite_w, 1.05, "F")
        pdf.set_xy(x + 3.2, y_boites + 2.6)
        pdf.set_font("Titre", "B", 15)
        pdf.set_text_color(*marine)
        pdf.cell(boite_w - 6, 7, nombre)
        pdf.set_xy(x + 3.2, y_boites + 10)
        pdf.set_font("Corps", "", 8.5)
        pdf.set_text_color(*muet)
        pdf.cell(boite_w - 6, 4, legend)
    pdf.set_y(y_boites + boite_h + 8)

    if not groupes:
        ecrire("Corps", "", 11, 6, "Aucun article dans cette fenêtre.", encre, pdf.l_margin, largeur)
    else:
        pdf.set_x(pdf.l_margin)
        pdf.set_font("Titre", "B", 12)
        pdf.set_text_color(*marine)
        pdf.cell(largeur, 7, "Sommaire")
        pdf.ln(8)
        for label, articles in groupes:
            if pdf.get_y() > pdf.h - 28:
                pdf.add_page()
            nom = _pdf_texte(label) or "Rubrique"
            compte = str(len(articles))
            pdf.set_font("Corps", "B", 10)
            compte_w = pdf.get_string_width(compte) + 1
            pdf.set_font("Corps", "", 10.5)
            pdf.set_text_color(*encre)
            nom_w = min(pdf.get_string_width(nom) + 1.5, largeur - compte_w - 8)
            y_ligne = pdf.get_y()
            pdf.set_xy(pdf.l_margin, y_ligne)
            pdf.cell(nom_w, 6, nom)
            pdf.set_draw_color(198, 190, 178)
            pdf.set_line_width(0.2)
            pdf.set_dash_pattern(0.25, 1.15)
            pdf.line(pdf.l_margin + nom_w + 1.2, y_ligne + 4.1, pdf.l_margin + largeur - compte_w - 1.2, y_ligne + 4.1)
            pdf.set_dash_pattern()
            pdf.set_xy(pdf.l_margin + largeur - compte_w, y_ligne)
            pdf.set_font("Corps", "B", 10.5)
            pdf.set_text_color(*marine)
            pdf.cell(compte_w, 6, compte, align="R")
            pdf.ln(6.4)
        pdf.ln(3)

    for label, articles in groupes:
        if pdf.get_y() > pdf.h - 52:
            pdf.add_page()
        elif pdf.get_y() > pdf.t_margin + 4:
            pdf.ln(3)
        nom = _pdf_texte(label) or "Rubrique"
        pdf.set_font("Titre", "B", 14)
        if pdf.get_string_width(nom) > largeur - 16:
            ecrire("Titre", "B", 14, 6.6, nom, marine, pdf.l_margin, largeur)
        else:
            pdf.set_x(pdf.l_margin)
            pdf.set_text_color(*marine)
            pdf.cell(largeur - 14, 8, nom)
            pdf.set_font("Corps", "", 9)
            pdf.set_text_color(*muet)
            pdf.cell(14, 8, str(len(articles)), align="R")
            pdf.ln(8)
        pdf.set_draw_color(206, 198, 186)
        pdf.set_line_width(0.25)
        pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
        pdf.ln(4)

        for article in articles:
            titre_article = _pdf_texte(article.get("titre") or "Sans titre")
            meta = "  ·  ".join(
                part
                for part in (
                    _pdf_texte(article.get("source") or ""),
                    _date_longue(article.get("date")),
                )
                if part
            )
            vus: set[str] = set()
            mots: list[str] = []
            for mot in article.get("mots") or []:
                net = _pdf_texte(mot)
                cle = sans_accents(net).lower().replace(" ", "")
                if not net or cle in vus:
                    continue
                vus.add(cle)
                mots.append(net)
                if len(mots) == 5:
                    break
            resume = _pdf_texte(_resume(article, 420))
            titre_plat = sans_accents(titre_article).lower()
            if resume and titre_plat and sans_accents(resume).lower().startswith(titre_plat[: min(48, len(titre_plat))]):
                resume = ""
            lien = article.get("lien") or ""
            h_titre = mesure("Titre", "B", 12, 5.5, titre_article, inner_w)
            h_meta = mesure("Corps", "", 8.5, 4.2, meta, inner_w)
            h_mots = len(lignes_mots(mots, inner_w)) * 5.8 if mots else 0
            h_resume = mesure("Corps", "", 10.5, 4.9, resume, inner_w)
            hauteur = 3.4 + h_titre
            if meta:
                hauteur += 1.1 + h_meta
            if mots:
                hauteur += 1.8 + h_mots
            if resume:
                hauteur += 1.7 + h_resume
            if lien:
                hauteur += 6.2
            hauteur += 3.6

            if pdf.get_y() + hauteur > pdf.h - 18 and hauteur < pdf.h - 36:
                pdf.add_page()
            x = pdf.l_margin
            y0 = pdf.get_y()
            pdf.set_fill_color(*ombre)
            pdf.rect(x + 0.45, y0 + 0.55, largeur, hauteur, "F")
            pdf.set_fill_color(*carte)
            pdf.rect(x, y0, largeur, hauteur, "F")
            pdf.set_fill_color(*cuivre)
            pdf.rect(x, y0, 1.15, hauteur, "F")

            pdf.set_auto_page_break(auto=False)
            curseur = y0 + 3.2
            pdf.set_xy(x + 4.2, curseur)
            ecrire("Titre", "B", 12, 5.5, titre_article, encre, x + 4.2, inner_w)
            curseur = pdf.get_y()
            if meta:
                curseur += 0.8
                pdf.set_xy(x + 4.2, curseur)
                ecrire("Corps", "", 8.5, 4.2, meta, muet, x + 4.2, inner_w)
                curseur = pdf.get_y()
            if mots:
                curseur += 1.5
                curseur = dessiner_mots(mots, x + 4.2, curseur, inner_w)
            if resume:
                curseur += 1.6
                pdf.set_xy(x + 4.2, curseur)
                ecrire("Corps", "", 10.5, 4.9, resume, (62, 56, 50), x + 4.2, inner_w)
                curseur = pdf.get_y()
            if lien:
                curseur += 1.5
                pdf.set_font("Corps", "B", 9)
                pdf.set_text_color(*marine)
                libelle = "Lire l'article"
                large_lien = pdf.get_string_width(libelle)
                pdf.set_xy(x + 4.2, curseur)
                pdf.cell(large_lien, 4.4, libelle, link=lien)
                pdf.set_draw_color(*marine)
                pdf.set_line_width(0.18)
                pdf.line(x + 4.2, curseur + 4.3, x + 4.2 + large_lien, curseur + 4.3)
            pdf.set_auto_page_break(auto=True, margin=18)
            pdf.set_y(y0 + hauteur + 3.2)

    return bytes(pdf.output())


def _manifeste() -> dict[str, Any]:
    if not MANIFESTE.exists():
        return {}
    try:
        return json.loads(MANIFESTE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _ecrire_manifeste(data: dict[str, Any]) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    MANIFESTE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _index(manifeste: dict[str, Any]) -> str:
    maintenant = datetime.now().strftime("%d/%m/%Y à %H:%M")
    blocs = []
    for fiche in manifeste.values():
        liens = []
        for cle, libelle in (("pdf", "PDF"), ("html", "lire dans le navigateur"), ("md", "Markdown")):
            nom = (fiche.get("fichiers") or {}).get(cle)
            if nom:
                liens.append(f'<a href="{escape(nom)}">{libelle}</a>')
        blocs.append(
            f"""<article>
<h2>{escape(fiche.get('titre') or '')}</h2>
<p>{escape(fiche.get('perimetre') or '')}</p>
<p class="liens">{' · '.join(liens)}</p>
<p class="meta">mis à jour le {escape(fiche.get('maj') or '')}</p>
</article>"""
        )
    contenu = "".join(blocs) or "<p>Aucun rapport publié pour le moment.</p>"
    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Veille 2</title>
<style>
*, *::before, *::after {{ box-sizing: border-box; }}
body {{ margin: 0; font: 1rem/1.45 "Segoe UI", sans-serif; background: #f4f1ea; color: #1c1917; overflow-wrap: anywhere; }}
header {{ background: #1c1917; color: #fff; padding: max(1.25rem, env(safe-area-inset-top)) 1rem 1.15rem; }}
h1 {{ margin: 0; font-size: clamp(1.45rem, 6vw, 2rem); }}
header p {{ margin: .4rem 0 0; opacity: .85; }}
main {{ max-width: 40rem; margin: 0 auto; padding: 1rem 1rem 2rem; }}
article {{ background: #fff; border-radius: 14px; padding: 1rem; margin: 0 0 1rem; box-shadow: 0 6px 18px rgba(0,0,0,.06); }}
h2 {{ margin: 0; font-size: 1.2rem; }}
.liens a {{ display: inline-block; margin: .35rem .8rem .35rem 0; padding: .35rem 0; min-height: 44px; color: #0f4c5c; font-weight: 650; }}
.meta {{ color: #57534e; font-size: .9rem; }}
</style>
</head>
<body>
<header>
<h1>Veille 2</h1>
<p>Mis à jour le {escape(maintenant)}</p>
</header>
<main>
{contenu}
</main>
</body>
</html>
"""


def _deposer(fichiers: list[tuple[str, bytes]]) -> None:
    acces = _identifiants()
    if not acces["utilisateur"] or not acces["mot_de_passe"]:
        raise RuntimeError("Identifiants FTP des Pages Perso manquants.")
    ftp = ftplib.FTP()
    ftp.connect(acces["hote"], 21, timeout=180)
    try:
        ftp.login(acces["utilisateur"], acces["mot_de_passe"])
        ftp.set_pasv(True)
        try:
            ftp.cwd(DOSSIER)
        except ftplib.error_perm:
            ftp.mkd(DOSSIER)
            ftp.cwd(DOSSIER)
        for nom, corps in fichiers:
            ftp.storbinary(f"STOR {nom}", BytesIO(corps))
    except ftplib.all_errors as exc:
        raise RuntimeError(f"Dépôt FTP refusé : {exc}") from exc
    finally:
        try:
            ftp.quit()
        except Exception:  # noqa: BLE001
            ftp.close()


def _produire(profil_id: str, jours: int, format_export: str) -> tuple[str, bytes]:
    fiche = magasin.profil(profil_id)
    if fiche is None:
        raise ValueError("Veille introuvable.")
    base = nom_base(profil_id, fiche["titre"])
    if format_export == "pdf":
        return f"{base}.pdf", rendre_pdf(profil_id, jours)
    if format_export == "html":
        return f"{base}.html", rendre_html(profil_id, jours).encode("utf-8")
    if format_export == "md":
        return f"{base}.md", rendre_markdown(profil_id, jours).encode("utf-8")
    raise ValueError("Format attendu : pdf, html ou md.")


def _noter(manifeste: dict[str, Any], fiche: dict[str, Any], format_export: str, nom: str) -> None:
    entree = manifeste.get(fiche["id"]) or {"fichiers": {}}
    entree["titre"] = fiche["titre"]
    entree["perimetre"] = fiche.get("perimetre") or ""
    entree["maj"] = datetime.now().strftime("%d/%m/%Y à %H:%M")
    entree.setdefault("fichiers", {})[format_export] = nom
    manifeste[fiche["id"]] = entree


def publier(profil_id: str, jours: int, format_export: str) -> dict[str, str]:
    format_export = format_export.lower().strip()
    fiche = magasin.profil(profil_id)
    if fiche is None:
        raise ValueError("Veille introuvable.")
    nom, corps = _produire(profil_id, jours, format_export)
    manifeste = _manifeste()
    _noter(manifeste, fiche, format_export, nom)
    index = _index(manifeste).encode("utf-8")
    _deposer([(nom, corps), ("index.html", index)])
    _ecrire_manifeste(manifeste)
    return {
        "url": f"{URL_BASE}/{DOSSIER}/{nom}",
        "index": f"{URL_BASE}/{DOSSIER}/",
        "nom": nom,
    }


def _publier_toutes() -> None:
    from veille_v2 import collecte

    profils = magasin.profils()
    formats = ("pdf", "html", "md")
    total = len(profils) * len(formats)
    collecte._poser(total=total, fait=0, message="Préparation de toutes les veilles")
    fichiers: list[tuple[str, bytes]] = []
    manifeste: dict[str, Any] = {}
    echecs: list[str] = []
    fait = 0
    for fiche in profils:
        jours = int(fiche.get("periode_jours") or 7)
        for format_export in formats:
            fait += 1
            collecte._poser(
                fait=fait - 1,
                message=f"{fiche['titre']} · {format_export.upper()} ({fait}/{total})",
            )
            try:
                nom, corps = _produire(fiche["id"], jours, format_export)
            except Exception as exc:  # noqa: BLE001
                echecs.append(f"{fiche['titre']} {format_export.upper()} : {exc}")
                collecte._poser(fait=fait)
                continue
            fichiers.append((nom, corps))
            _noter(manifeste, fiche, format_export, nom)
            collecte._poser(fait=fait)
    if not fichiers:
        raise RuntimeError(echecs[0] if echecs else "Aucun rapport à publier.")
    fichiers.append(("index.html", _index(manifeste).encode("utf-8")))
    collecte._poser(message="Dépôt de toutes les veilles sur les Pages Perso")
    _deposer(fichiers)
    _ecrire_manifeste(manifeste)
    if echecs:
        collecte.liberer(
            f"{len(manifeste)} veilles déposées, {len(echecs)} fichier(s) en échec",
            " · ".join(echecs[:6]),
        )
        return
    collecte.liberer(f"{len(profils)} veilles publiées en PDF, HTML et Markdown")


def demarrer_toutes() -> bool:
    from veille_v2 import collecte

    if not collecte.occuper("export", "Export de toutes les veilles"):
        return False

    def _lancer() -> None:
        from veille_v2 import collecte as suivi

        try:
            _publier_toutes()
        except Exception as exc:  # noqa: BLE001
            suivi.liberer("Export interrompu", str(exc))

    threading.Thread(target=_lancer, daemon=True).start()
    return True
