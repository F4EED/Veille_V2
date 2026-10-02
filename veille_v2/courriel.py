"""Envoi des veilles par courriel, adresse par adresse."""

from __future__ import annotations

import os
import re
import smtplib
import ssl
import threading
from email.message import EmailMessage
from html import escape
from typing import Any

from veille_v2 import collecte, export, filtre, magasin
from veille_v2.export import URL_BASE, _charger
from veille_v2.seed import V1

PAGE = f"{URL_BASE}/Veille_2/"
_ADRESSE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
ARTICLES_PAR_VEILLE = 8


def valider(email: str) -> str:
    adresse = email.strip().lower()
    if not _ADRESSE.match(adresse):
        raise ValueError("Adresse courriel invalide.")
    return adresse


def carnet() -> dict[str, Any]:
    cfg, smtp, _mot = _acces()
    return {
        "courriels": magasin.courriels(),
        "expediteur": str(cfg.get("expediteur") or smtp.get("utilisateur") or ""),
        "pret": bool(smtp.get("hote") and _mot),
    }


def definir(email: str, profils: list[str]) -> dict[str, Any]:
    adresse = valider(email)
    connus = {fiche["id"] for fiche in magasin.profils()}
    gardes = [profil for profil in profils if str(profil) in connus]
    magasin.enregistrer_courriel(adresse, gardes)
    return carnet()


def retirer(email: str) -> dict[str, Any]:
    magasin.retirer_courriel(valider(email))
    return carnet()


def demarrer(email: str = "") -> bool:
    if not collecte.occuper("courriel", "Envoi des courriels"):
        return False
    threading.Thread(target=_job, args=(email.strip().lower(),), daemon=True).start()
    return True


def _acces() -> tuple[dict[str, Any], dict[str, Any], str]:
    cfg = _charger(V1 / "email.yaml")
    secrets = _charger(V1 / "email.secrets.yaml")
    smtp = dict(cfg.get("smtp") or {})
    mot = os.environ.get("VEILLE_SMTP_PASSWORD") or secrets.get("mot_de_passe") or ""
    return cfg, smtp, str(mot).strip()


def _job(email: str) -> None:
    try:
        message = _envoyer(email)
    except Exception as exc:  # noqa: BLE001
        collecte.liberer(f"Courriel interrompu : {exc}", str(exc))
        return
    collecte.liberer(message)


def _envoyer(email: str) -> str:
    cfg, smtp, mot = _acces()
    if not str(smtp.get("hote") or "").strip():
        raise RuntimeError("Serveur SMTP absent de la veille d'origine.")
    if not mot:
        raise RuntimeError("Mot de passe SMTP absent.")
    utilisateur = str(smtp.get("utilisateur") or cfg.get("expediteur") or "").strip()
    if not utilisateur:
        raise RuntimeError("Expéditeur SMTP absent.")
    lignes = magasin.courriels()
    if email:
        lignes = [ligne for ligne in lignes if ligne["email"] == email]
        if not lignes:
            raise RuntimeError("Cette adresse n'est pas dans le carnet.")
    a_envoyer = [ligne for ligne in lignes if ligne["profils"]]
    if not a_envoyer:
        raise RuntimeError("Aucune veille cochée.")
    collecte._poser(total=len(a_envoyer), fait=0)
    envois = 0
    erreurs: list[str] = []
    for index, ligne in enumerate(a_envoyer, 1):
        collecte._poser(fait=index - 1, message=f"Courriel {index} / {len(a_envoyer)} · {ligne['email']}")
        try:
            _poster(ligne, cfg, smtp, utilisateur, mot)
            envois += 1
        except Exception as exc:  # noqa: BLE001
            erreurs.append(f"{ligne['email']} : {exc}")
    collecte._poser(fait=len(a_envoyer))
    if erreurs and not envois:
        raise RuntimeError(" ; ".join(erreurs))
    texte = f"Courriel envoyé à {envois} adresse{'s' if envois > 1 else ''}"
    if erreurs:
        texte += " · " + " ; ".join(erreurs)
    return texte


def _poster(
    ligne: dict[str, Any],
    cfg: dict[str, Any],
    smtp: dict[str, Any],
    utilisateur: str,
    mot: str,
) -> None:
    fiches = []
    for profil_id in ligne["profils"]:
        fiche = magasin.profil(profil_id)
        if fiche is None:
            continue
        jours = int(fiche["periode_jours"] or 7)
        data = filtre.lister(profil_id, jours, limite=ARTICLES_PAR_VEILLE, resume_max=160)
        fiches.append((fiche, data))
    if not fiches:
        raise RuntimeError("aucune veille à envoyer")
    titres = [fiche["titre"] for fiche, _data in fiches]
    sujet = "Veille — " + ", ".join(titres[:3])
    if len(titres) > 3:
        sujet += f" et {len(titres) - 3} autre{'s' if len(titres) > 4 else ''}"
    html_complet, texte = _corps(fiches)
    _transmettre(ligne["email"], sujet, texte, html_complet, cfg, smtp, utilisateur, mot)


def _corps(fiches: list[tuple[dict[str, Any], dict[str, Any]]]) -> tuple[str, str]:
    blocs_html: list[str] = []
    blocs_texte: list[str] = []
    for fiche, data in fiches:
        nom = export.nom_base(fiche["id"], fiche["titre"])
        pdf = f"{PAGE}{nom}.pdf"
        page = f"{PAGE}{nom}.html"
        md = f"{PAGE}{nom}.md"
        titre = escape(fiche["titre"])
        total = int(data.get("total") or 0)
        jours = int(fiche["periode_jours"] or 7)
        articles = data.get("articles") or []
        lignes = []
        texte_articles = []
        for article in articles:
            lien = article.get("lien") or ""
            titre_article = escape(article.get("titre") or "Sans titre")
            if lien:
                lignes.append(f'<li><a href="{escape(lien)}">{titre_article}</a></li>')
                texte_articles.append(f"- {article.get('titre') or 'Sans titre'}\n  {lien}")
            else:
                lignes.append(f"<li>{titre_article}</li>")
                texte_articles.append(f"- {article.get('titre') or 'Sans titre'}")
        liste = f"<ul>{''.join(lignes)}</ul>" if lignes else "<p>Aucun article dans la fenêtre.</p>"
        blocs_html.append(
            "<section>"
            f"<h2>{titre}</h2>"
            f"<p>{total} article{'s' if total > 1 else ''} · {jours} jours</p>"
            f'<p><a href="{pdf}">PDF</a> · <a href="{page}">HTML</a> · <a href="{md}">Markdown</a></p>'
            f"{liste}</section>"
        )
        blocs_texte.append(
            f"{fiche['titre']} — {total} articles, {jours} jours\n"
            f"PDF {pdf}\nHTML {page}\nMarkdown {md}\n"
            + ("\n".join(texte_articles) if texte_articles else "Aucun article dans la fenêtre.")
        )
    html_doc = (
        "<!DOCTYPE html><html lang=\"fr\"><body "
        "style=\"font-family:Georgia,serif;line-height:1.45;color:#1c1917;\">"
        f"<p>Veilles choisies pour cette adresse. Toutes les veilles : <a href=\"{PAGE}\">{PAGE}</a></p>"
        + "".join(blocs_html)
        + "</body></html>"
    )
    texte = f"Toutes les veilles : {PAGE}\n\n" + "\n\n".join(blocs_texte)
    return html_doc, texte


def _transmettre(
    destinataire: str,
    sujet: str,
    texte: str,
    html_doc: str,
    cfg: dict[str, Any],
    smtp: dict[str, Any],
    utilisateur: str,
    mot: str,
) -> None:
    expediteur = str(cfg.get("expediteur") or utilisateur)
    nom = str(cfg.get("expediteur_nom") or "Veille")
    essais = [html_doc, _sans_liens_articles(html_doc)]
    derniere: Exception | None = None
    for variante in essais:
        message = EmailMessage()
        message["Subject"] = sujet
        message["From"] = f"{nom} <{expediteur}>"
        message["To"] = destinataire
        message.set_content(texte if variante == html_doc else _texte_sans_articles(texte))
        message.add_alternative(variante, subtype="html")
        try:
            _smtp(message, smtp, utilisateur, mot)
            return
        except Exception as exc:  # noqa: BLE001
            derniere = exc
            if "550" not in str(exc).lower() or "spam" not in str(exc).lower():
                raise
    if derniere:
        raise derniere


def _sans_liens_articles(html_doc: str) -> str:
    return re.sub(r"<ul>.*?</ul>", "<p>Les titres sont dans le PDF en ligne.</p>", html_doc, flags=re.S)


def _texte_sans_articles(texte: str) -> str:
    lignes = []
    for ligne in texte.splitlines():
        if ligne.startswith("- ") or ligne.startswith("  http"):
            continue
        lignes.append(ligne)
    return "\n".join(lignes)


def _smtp(message: EmailMessage, smtp: dict[str, Any], utilisateur: str, mot: str) -> None:
    hote = str(smtp.get("hote") or "").strip()
    port = int(smtp.get("port") or 587)
    contexte = ssl.create_default_context()
    if smtp.get("ssl"):
        with smtplib.SMTP_SSL(hote, port, timeout=40, context=contexte) as serveur:
            serveur.login(utilisateur, mot)
            serveur.send_message(message)
        return
    with smtplib.SMTP(hote, port, timeout=40) as serveur:
        serveur.ehlo()
        if smtp.get("demarrer_tls", True):
            serveur.starttls(context=contexte)
            serveur.ehlo()
        serveur.login(utilisateur, mot)
        serveur.send_message(message)
