"""Téléchargement parallèle des flux, une fois pour toutes les veilles."""

from __future__ import annotations

import hashlib
import html
import re
import threading
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from time import perf_counter
from typing import Any

import feedparser

from veille_v2 import magasin
from veille_v2.texte import normaliser

USER_AGENT = "Mozilla/5.0 (compatible; VeilleVive/2.0; outil local de veille)"
TIMEOUT_S = 8
MAX_WORKERS = 24
LIMITE_PAR_HOTE = {
    "news.google.com": 6,
    "github.com": 6,
}
_limiteurs: dict[str, threading.BoundedSemaphore] = {}
_limiteurs_lock = threading.Lock()

job_lock = threading.Lock()
job: dict[str, Any] = {
    "actif": False,
    "type": "",
    "fait": 0,
    "total": 0,
    "message": "Aucune collecte",
    "erreur": "",
    "nouvelles": 0,
}


def etat_job() -> dict[str, Any]:
    with job_lock:
        return dict(job)


def _poser(**kwargs: Any) -> None:
    with job_lock:
        job.update(kwargs)


def occuper(type_job: str, message: str) -> bool:
    with job_lock:
        if job["actif"]:
            return False
        job.update(
            {
                "actif": True,
                "type": type_job,
                "fait": 0,
                "total": 0,
                "message": message,
                "erreur": "",
                "nouvelles": 0,
            }
        )
        return True


def liberer(message: str, erreur: str = "") -> None:
    _poser(actif=False, message=message, erreur=erreur)


def _hote(url: str) -> str:
    from urllib.parse import urlparse

    hote = urlparse(url).netloc.lower()
    return hote[4:] if hote.startswith("www.") else hote


def _limiteur(url: str) -> threading.BoundedSemaphore:
    hote = _hote(url)
    with _limiteurs_lock:
        limiteur = _limiteurs.get(hote)
        if limiteur is None:
            limiteur = threading.BoundedSemaphore(LIMITE_PAR_HOTE.get(hote, 12))
            _limiteurs[hote] = limiteur
        return limiteur


def nettoyer_html(raw: str) -> str:
    texte = re.sub(r"(?is)<script.*?>.*?</script>", " ", raw or "")
    texte = re.sub(r"(?is)<style.*?>.*?</style>", " ", texte)
    texte = re.sub(r"(?s)<[^>]+>", " ", texte)
    return re.sub(r"\s+", " ", html.unescape(texte)).strip()


def _date_entree(entry: Any) -> str | None:
    for attr in ("published_parsed", "updated_parsed"):
        parsed = entry.get(attr)
        if parsed:
            try:
                return datetime(*parsed[:6], tzinfo=timezone.utc).isoformat()
            except (TypeError, ValueError):
                pass
    for attr in ("published", "updated"):
        valeur = entry.get(attr)
        if not valeur:
            continue
        try:
            dt = parsedate_to_datetime(str(valeur))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc).isoformat()
        except (TypeError, ValueError, OverflowError):
            continue
    return None


def telecharger(
    url: str,
    etag: str = "",
    last_modified: str = "",
    timeout: int = TIMEOUT_S,
    user_agent: str = "",
) -> tuple[int, bytes, str, str]:
    """Retourne (code, corps, etag, last_modified). 304 → corps vide."""
    headers = {
        "User-Agent": user_agent or USER_AGENT,
        "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, text/html, */*",
    }
    if etag:
        headers["If-None-Match"] = etag
    if last_modified:
        headers["If-Modified-Since"] = last_modified
    requete = urllib.request.Request(url, headers=headers)
    limiteur = _limiteur(url)
    limiteur.acquire()
    try:
        try:
            with urllib.request.urlopen(requete, timeout=timeout) as reponse:
                return (
                    getattr(reponse, "status", 200),
                    reponse.read(2_000_000),
                    reponse.headers.get("ETag") or etag,
                    reponse.headers.get("Last-Modified") or last_modified,
                )
        except urllib.error.HTTPError as exc:
            if exc.code == 304:
                return 304, b"", etag, last_modified
            raise
    finally:
        limiteur.release()


def _lien(entry: Any) -> str:
    lien = str(entry.get("link") or "").strip()
    if lien:
        return lien
    for candidate in entry.get("links") or []:
        href = candidate.get("href")
        if href:
            return str(href).strip()
    return ""


def _resume(entry: Any) -> str:
    for cle in ("summary", "description"):
        if entry.get(cle):
            return nettoyer_html(str(entry.get(cle)))[:1200]
    return ""


def _identifiant(source_id: str, lien: str, titre: str) -> str:
    base = lien.split("?")[0].strip().lower() or f"{source_id}|{normaliser(titre)}"
    return hashlib.sha1(base.encode("utf-8")).hexdigest()[:24]


def lire_source(source: dict[str, Any]) -> tuple[str, int, str]:
    debut = perf_counter()
    maintenant = datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        code, corps, etag, last_modified = telecharger(
            source["url"], source.get("etag") or "", source.get("last_modified") or ""
        )
    except Exception as exc:  # noqa: BLE001
        magasin.maj_source_fetch(
            source["id"],
            etag=source.get("etag") or "",
            last_modified=source.get("last_modified") or "",
            dernier_ok=source.get("dernier_ok") or "",
            erreur=str(exc),
            duree_ms=int((perf_counter() - debut) * 1000),
            nb_entrees=0,
        )
        return source["nom"], 0, str(exc)

    if code == 304:
        magasin.maj_source_fetch(
            source["id"],
            etag=etag,
            last_modified=last_modified,
            dernier_ok=maintenant,
            erreur="",
            duree_ms=int((perf_counter() - debut) * 1000),
            nb_entrees=int(source.get("nb_entrees") or 0),
        )
        return source["nom"], 0, ""

    flux = feedparser.parse(corps)
    lignes = []
    for entry in (flux.entries or [])[:40]:
        titre = nettoyer_html(str(entry.get("title") or "")).strip()
        if not titre:
            continue
        date_pub = _date_entree(entry)
        if date_pub and date_pub < "2025-01-01":
            continue
        resume = _resume(entry)
        lien = _lien(entry)
        editeur = entry.get("source") or {}
        editeur_nom = ""
        editeur_url = ""
        if isinstance(editeur, dict):
            editeur_nom = nettoyer_html(str(editeur.get("title") or ""))
            editeur_url = str(editeur.get("href") or "")
        lignes.append(
            (
                _identifiant(source["id"], lien, titre),
                source["id"],
                titre[:300],
                lien[:800],
                resume,
                date_pub,
                normaliser(f"{titre} {resume}"),
                editeur_nom[:160],
                editeur_url[:400],
                maintenant,
            )
        )
    if not lignes and getattr(flux, "bozo", False):
        erreur = "flux illisible"
        magasin.maj_source_fetch(
            source["id"],
            etag=etag,
            last_modified=last_modified,
            dernier_ok="",
            erreur=erreur,
            duree_ms=int((perf_counter() - debut) * 1000),
            nb_entrees=0,
        )
        return source["nom"], 0, erreur
    nouvelles = magasin.inserer_articles(lignes)
    magasin.maj_source_fetch(
        source["id"],
        etag=etag,
        last_modified=last_modified,
        dernier_ok=maintenant,
        erreur="",
        duree_ms=int((perf_counter() - debut) * 1000),
        nb_entrees=len(lignes),
    )
    return source["nom"], nouvelles, ""


def lancer(plafond: int | None = None) -> None:
    from veille_v2 import reseaux

    _poser(message="Recherches X, Instagram et Snap")
    reseaux.synchroniser()
    sources = magasin.sources_actives()
    if plafond:
        sources = sources[:plafond]
    _poser(total=len(sources), fait=0, message=f"0 / {len(sources)} flux")
    nouvelles = 0
    erreurs = 0
    if not sources:
        liberer("Aucune source à lire")
        return
    with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(sources))) as pool:
        futurs = [pool.submit(lire_source, source) for source in sources]
        for futur in as_completed(futurs):
            _nom, ajoutees, erreur = futur.result()
            nouvelles += ajoutees
            if erreur:
                erreurs += 1
            with job_lock:
                job["fait"] += 1
                job["nouvelles"] = nouvelles
                job["message"] = f"{job['fait']} / {job['total']} flux · {nouvelles} articles nouveaux"
    liberer(f"Collecte terminée · {nouvelles} articles nouveaux · {erreurs} flux en erreur")


def demarrer(plafond: int | None = None) -> bool:
    if not occuper("collecte", "Préparation de la collecte"):
        return False
    fil = threading.Thread(target=lancer, args=(plafond,), daemon=True)
    fil.start()
    return True
