"""Recherche réactive : un mot tout de suite, ou un radar de nouveaux flux."""

from __future__ import annotations

import re
import threading
import urllib.parse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import feedparser

from veille_v2 import collecte, magasin
from veille_v2.texte import compiler, mots_trouves, normaliser

HOTES_IGNORES = {
    "amazon.com",
    "apple.com",
    "bing.com",
    "doubleclick.net",
    "facebook.com",
    "feedspot.com",
    "feedly.com",
    "google.com",
    "google.fr",
    "duckduckgo.com",
    "yahoo.com",
    "msn.com",
    "instagram.com",
    "snapchat.com",
    "linkedin.com",
    "microsoft.com",
    "news.google.com",
    "pinterest.com",
    "reddit.com",
    "t.co",
    "tiktok.com",
    "twitter.com",
    "wikipedia.org",
    "x.com",
    "youtube.com",
    "bsky.app",
    "threads.net",
    "mastodon.social",
    "piaille.fr",
    "fosstodon.org",
}

CHEMINS = (
    "/feed",
    "/feed/",
    "/rss",
    "/rss/",
    "/feed.xml",
    "/rss.xml",
    "/atom.xml",
    "/index.xml",
    "/feed/rss",
    "/blog/feed",
    "/blog/rss.xml",
    "/feeds/posts/default",
    "/?feed=rss2",
)
UA_PAGE = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)
VIDES = {
    "avec",
    "dans",
    "pour",
    "sans",
    "sous",
    "sur",
    "the",
    "and",
    "for",
    "from",
    "news",
    "blog",
}
HREF = re.compile(r"""href\s*=\s*["']([^"']+)["']""", re.IGNORECASE)
TYPE_FLUX = re.compile(r"application/(?:rss|atom)\+xml", re.IGNORECASE)
BALISE_LIEN = re.compile(r"<link\b[^>]*>", re.IGNORECASE)
BALISE_A = re.compile(r"<a\b[^>]*>", re.IGNORECASE)
MAUVAIS_CHEMIN = ("/comment", "/tag/", "/category/", "/author/", "/label/", "/search")


def hote(url: str) -> str:
    nom = urllib.parse.urlparse(url).netloc.lower()
    return nom[4:] if nom.startswith("www.") else nom


def hote_interdit(nom: str) -> bool:
    return any(nom == bloque or nom.endswith("." + bloque) for bloque in HOTES_IGNORES)


def _slug(texte: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", normaliser(texte)).strip("-") or "mot"


def chercher_mot(profil_id: str, mot: str, domaine: str = "") -> dict[str, Any]:
    mot = mot.strip()
    if len(mot) < 2:
        return {"erreur": "Mot trop court."}
    from veille_v2.seed import url_google_news

    adresse = url_google_news(mot, "fr", "FR", "FR:fr")
    identifiant = f"live-{profil_id}-{_slug(mot)}"[:80]
    existante = magasin.source_par_url(adresse)
    if existante is None:
        magasin.enregistrer_source(
            {
                "id": identifiant,
                "nom": f"Recherche — {mot}",
                "url": adresse,
                "site": "https://news.google.com/",
                "kind": "live",
                "filtre": "aucun",
                "domaine": domaine,
                "profils": [profil_id],
                "ignorer_date": True,
                "requete": mot,
            }
        )
    magasin.orienter_recherche(adresse, domaine, profil_id)
    existante = magasin.source_par_url(adresse)
    if existante is None:
        return {"erreur": "Impossible d'enregistrer la recherche."}
    nom, ajoutees, erreur = collecte.lire_source(existante)
    del nom
    hotes = _hotes_frais(mot)
    return {"ajoutees": ajoutees, "erreur": erreur, "hotes": hotes, "mot": mot}


def _hotes_frais(mot: str) -> list[dict[str, str]]:
    mot_compile = compiler(mot)
    if mot_compile is None:
        return []
    connus = magasin.hotes_connus()
    compteur: Counter[str] = Counter()
    noms: dict[str, str] = {}
    with magasin.connecter() as conn:
        rows = conn.execute(
            """
            SELECT editeur_nom, editeur_url, titre, texte_norm
            FROM articles
            WHERE editeur_url != ''
            ORDER BY recupere DESC
            LIMIT 800
            """
        ).fetchall()
    for row in rows:
        if not mot_compile.present(row["texte_norm"]) and mot_compile.normalise not in normaliser(row["titre"]):
            continue
        nom_hote = hote(row["editeur_url"])
        if not nom_hote or hote_interdit(nom_hote) or nom_hote in connus:
            continue
        compteur[nom_hote] += 1
        noms.setdefault(nom_hote, row["editeur_nom"] or nom_hote)
    return [
        {"hote": nom, "nom": noms[nom], "mentions": str(n)}
        for nom, n in compteur.most_common(8)
    ]


def _flux_dans_page(page: str, base: str) -> list[str]:
    trouves: list[str] = []
    extrait = page[:120_000]

    def ajouter(tag: str, lien: str) -> None:
        if not lien or lien.startswith(("#", "javascript:", "mailto:")):
            return
        absolu = urllib.parse.urljoin(base, lien)
        if _chemin_inutile(absolu):
            return
        trouves.append(absolu)

    for balise in BALISE_LIEN.finditer(extrait):
        tag = balise.group(0)
        if re.search(r"stylesheet", tag, re.IGNORECASE):
            continue
        href = HREF.search(tag)
        if not href:
            continue
        if TYPE_FLUX.search(tag) or _semble_flux(href.group(1)):
            ajouter(tag, href.group(1))
    for balise in BALISE_A.finditer(extrait):
        tag = balise.group(0)
        href = HREF.search(tag)
        if not href:
            continue
        lien = href.group(1).lower()
        if any(cle in lien for cle in ("/feed", "/rss", "atom.xml", "rss.xml", "feed.xml")):
            ajouter(tag, href.group(1))
    return trouves


def _chemin_inutile(url: str) -> bool:
    chemin = urllib.parse.urlparse(url).path.lower()
    return any(morceau in chemin for morceau in MAUVAIS_CHEMIN)


def _semble_flux(url: str) -> bool:
    chemin = urllib.parse.urlparse(url).path.lower()
    question = urllib.parse.urlparse(url).query.lower()
    return any(cle in chemin or cle in question for cle in ("feed", "rss", "atom", ".xml"))


def _score_flux(titres: list[str], nom_flux: str, mots: list[Any]) -> int:
    score = 0
    for titre in titres:
        hits = mots_trouves(normaliser(titre), mots)
        if hits:
            score += 1 + len(hits)
    if nom_flux and mots_trouves(normaliser(nom_flux), mots):
        score += 2
    return score


def _lire_page(url: str, timeout: int = 6) -> bytes:
    _code, corps, _etag, _lm = collecte.telecharger(url, timeout=timeout, user_agent=UA_PAGE)
    return corps or b""


def examiner(site: str, profil_id: str, mots: list[Any] | None = None, pourquoi: str = "") -> dict[str, Any]:
    """Cherche le flux le plus proche de la veille, sans l'enregistrer."""
    brut = site if site.startswith("http") else f"https://{site}"
    parsed = urllib.parse.urlparse(brut)
    if not parsed.netloc:
        return {"erreur": "Adresse invalide."}
    origine = f"{parsed.scheme}://{parsed.netloc}".rstrip("/")
    if mots is None:
        from veille_v2.filtre import modele as modele_fn

        modele = modele_fn(profil_id)
        mots = [mot for domaine in modele["domaines"] for mot in domaine["mots"]]
    candidats_url: list[str] = []
    if _semble_flux(brut):
        candidats_url.append(brut.split("#", 1)[0])
    pages = []
    if parsed.path not in ("", "/"):
        pages.append(brut.split("#", 1)[0])
    pages.append(origine + "/")
    if hote(origine) == "github.com":
        morceaux = [part for part in parsed.path.split("/") if part]
        if len(morceaux) >= 2:
            depot = f"https://github.com/{morceaux[0]}/{morceaux[1]}"
            candidats_url.append(depot + "/releases.atom")
            candidats_url.append(depot + "/commits.atom")
    for page in pages:
        try:
            corps = _lire_page(page, timeout=6)
        except Exception:
            continue
        if corps:
            candidats_url.extend(_flux_dans_page(corps.decode("utf-8", errors="ignore"), page))
    if not any(_semble_flux(url) for url in candidats_url):
        for chemin in CHEMINS:
            candidats_url.append(origine + chemin)
    vus: set[str] = set()
    meilleur: dict[str, Any] | None = None
    essais = 0
    for url in candidats_url:
        url = url.split("#", 1)[0]
        if url in vus or _chemin_inutile(url):
            continue
        vus.add(url)
        essais += 1
        if essais > 8:
            break
        try:
            corps = _lire_page(url, timeout=6)
        except Exception:
            continue
        if not corps or corps[:1] not in (b"<", b"\xef", b"\n", b" ", b"\r", b"{"):
            if not corps.startswith(b"<?xml") and b"<rss" not in corps[:500].lower() and b"<feed" not in corps[:500].lower():
                continue
        flux = feedparser.parse(corps)
        if len(flux.entries or []) < 2:
            continue
        titres = [collecte.nettoyer_html(str(e.get("title") or "")).strip() for e in flux.entries[:8]]
        titres = [t for t in titres if t]
        nom = ""
        if getattr(flux, "feed", None):
            nom = collecte.nettoyer_html(str(flux.feed.get("title") or "")).strip()
        score = _score_flux(titres, nom, mots)
        fiche = {
            "url": url,
            "nom": nom or hote(origine),
            "site": origine + "/",
            "profil_id": profil_id,
            "raison": pourquoi or f"Flux trouvé sur {hote(origine)}",
            "echantillon": titres[:4],
            "score": score,
        }
        if meilleur is None or score > int(meilleur["score"]):
            meilleur = fiche
        if score >= 4:
            break
    if meilleur is None:
        return {"erreur": f"Pas de flux RSS sur {hote(origine)}."}
    if meilleur["score"]:
        meilleur["raison"] = f"{meilleur['raison']} · pertinence {meilleur['score']}"
    else:
        meilleur["raison"] = f"{meilleur['raison']} · flux trouvé, titres hors des mots de la veille"
    return meilleur


def sonder(site: str, profil_id: str, seuil: int = 0) -> dict[str, Any]:
    fiche = examiner(site, profil_id)
    if "url" not in fiche:
        return fiche
    if int(fiche.get("score") or 0) < seuil:
        return {"erreur": f"Flux hors sujet sur {hote(site)}.", "score": fiche.get("score") or 0}
    magasin.enregistrer_candidat(fiche)
    return fiche


def _deja_traites() -> set[str]:
    connus = magasin.hotes_connus()
    with magasin.connecter() as conn:
        rows = conn.execute("SELECT url, site FROM candidats").fetchall()
    for row in rows:
        for valeur in (row["url"], row["site"]):
            nom = hote(valeur or "")
            if nom:
                connus.add(nom)
    return connus


def _interet_requete(brut: str) -> int:
    clair = normaliser(brut)
    morceaux = clair.split()
    if not clair or len(clair) > 42 or len(morceaux) > 3:
        return -1
    score = 0
    if len(morceaux) == 1 and 5 <= len(clair) <= 18:
        score += 6
    elif len(morceaux) == 2:
        score += 5
    else:
        score += 2
    if any(caractere.isupper() for caractere in brut[1:]):
        score += 3
    return score


def _meilleur_mot(phrases: list[str], tokens: list[str]) -> str:
    candidats = [mot for mot in phrases + tokens if _interet_requete(mot) >= 2]
    if not candidats:
        return ""
    return max(candidats, key=_interet_requete)


def _choisir_requetes(profil_id: str) -> list[str]:
    from veille_v2.filtre import modele as modele_fn

    modele = modele_fn(profil_id)
    phrases: list[str] = []
    tokens: list[str] = []
    for domaine in modele["domaines"]:
        locales_phrases: list[str] = []
        locaux: list[str] = []
        for mot in domaine["mots"]:
            clair = mot.normalise
            if len(clair) < 4 or clair in VIDES:
                continue
            if " " in clair or "-" in clair:
                locales_phrases.append(mot.brut.strip())
            elif len(clair) >= 5:
                locaux.append(mot.brut.strip())
        retenu = _meilleur_mot(locales_phrases, locaux)
        if retenu:
            (phrases if " " in normaliser(retenu) or "-" in normaliser(retenu) else tokens).append(retenu)
    choix: list[str] = []
    vus: set[str] = set()
    for brut in sorted(phrases + tokens, key=_interet_requete, reverse=True):
        cle = normaliser(brut)
        if cle in vus:
            continue
        vus.add(cle)
        choix.append(brut)
        if len(choix) >= 6:
            break
    return choix


def _page_plus_precise(ancienne: str, nouvelle: str) -> str:
    if not ancienne:
        return nouvelle
    ancien_chemin = urllib.parse.urlparse(ancienne).path
    nouveau_chemin = urllib.parse.urlparse(nouvelle).path
    if nouveau_chemin.count("/") > ancien_chemin.count("/"):
        return nouvelle
    return ancienne


def _noter_piste(
    pistes: dict[str, dict[str, Any]],
    url: str,
    nom: str,
    poids: int,
    pourquoi: str,
    connus: set[str],
) -> None:
    nom_hote = hote(url)
    if not nom_hote or hote_interdit(nom_hote) or nom_hote in connus:
        return
    fiche = pistes.get(nom_hote)
    if fiche is None:
        pistes[nom_hote] = {
            "hote": nom_hote,
            "nom": nom or nom_hote,
            "poids": poids,
            "pourquoi": [pourquoi],
            "direct": url if _semble_flux(url) else "",
            "page": "" if _semble_flux(url) else url,
        }
        return
    fiche["poids"] += poids
    if pourquoi not in fiche["pourquoi"]:
        fiche["pourquoi"].append(pourquoi)
    if not fiche["direct"] and _semble_flux(url):
        fiche["direct"] = url
    if not _semble_flux(url):
        fiche["page"] = _page_plus_precise(fiche.get("page") or "", url)
    if nom and fiche["nom"] == nom_hote:
        fiche["nom"] = nom


def _editeurs_google(requete: str) -> list[tuple[str, str]]:
    from veille_v2.seed import url_google_news

    langues = [("fr", "FR", "FR:fr")]
    if requete.isascii():
        langues.append(("en", "US", "US:en"))
    trouves: list[tuple[str, str]] = []
    for hl, gl, ceid in langues:
        try:
            corps = _lire_page(url_google_news(requete, hl, gl, ceid), timeout=8)
        except Exception:
            continue
        if not corps:
            continue
        flux = feedparser.parse(corps)
        for entry in (flux.entries or [])[:12]:
            source = entry.get("source") or {}
            if not isinstance(source, dict):
                continue
            adresse = str(source.get("href") or "")
            titre = collecte.nettoyer_html(str(source.get("title") or ""))
            if adresse:
                trouves.append((adresse, titre))
    return trouves


def _sites_web(requete: str) -> list[str]:
    requete_web = urllib.parse.urlencode({"q": f'"{requete}" (rss OR feed)'})
    adresse = f"https://html.duckduckgo.com/html/?{requete_web}"
    try:
        corps = _lire_page(adresse, timeout=7)
    except Exception:
        return []
    if not corps:
        return []
    page = corps.decode("utf-8", errors="ignore")
    urls: list[str] = []
    for balise in BALISE_A.finditer(page):
        tag = balise.group(0)
        if "result__a" not in tag and "uddg=" not in tag:
            continue
        href = HREF.search(tag)
        if not href:
            continue
        lien = href.group(1)
        if lien.startswith("//"):
            lien = "https:" + lien
        if "uddg=" in lien:
            query = urllib.parse.parse_qs(urllib.parse.urlparse(lien).query)
            lien = (query.get("uddg") or [""])[0]
        if lien.startswith("http"):
            urls.append(lien)
        if len(urls) >= 8:
            break
    return urls


def _pistes_locales(mots: list[Any], connus: set[str], pistes: dict[str, dict[str, Any]]) -> None:
    with magasin.connecter() as conn:
        rows = conn.execute(
            """
            SELECT a.editeur_nom, a.editeur_url, a.texte_norm
            FROM articles a
            JOIN sources s ON s.id = a.source_id
            WHERE a.editeur_url != '' AND s.kind IN ('google_news', 'reseau', 'live')
            ORDER BY a.recupere DESC
            LIMIT 1500
            """
        ).fetchall()
    for row in rows:
        if not mots_trouves(row["texte_norm"], mots):
            continue
        _noter_piste(pistes, row["editeur_url"], row["editeur_nom"] or "", 1, "articles déjà lus", connus)


def _radar(profil_id: str) -> None:
    from veille_v2.filtre import modele as modele_fn

    modele = modele_fn(profil_id)
    mots = [mot for domaine in modele["domaines"] for mot in domaine["mots"]]
    requetes = _choisir_requetes(profil_id)
    connus = _deja_traites()
    pistes: dict[str, dict[str, Any]] = {}
    collecte._poser(total=max(len(requetes), 1), fait=0, message="Recherche de nouveaux sites")
    if requetes:
        with ThreadPoolExecutor(max_workers=6) as pool:
            futurs_google = [pool.submit(_editeurs_google, requete) for requete in requetes]
            futurs_web = [pool.submit(_sites_web, requete) for requete in requetes[:4]]
            google = [futur.result() for futur in futurs_google]
            web = [futur.result() for futur in futurs_web]
        for requete, editeurs in zip(requetes, google):
            for adresse, nom in editeurs:
                _noter_piste(pistes, adresse, nom, 3, f"Google News · {requete}", connus)
        for requete, liens in zip(requetes[:4], web):
            for adresse in liens:
                _noter_piste(pistes, adresse, "", 2, f"Web · {requete}", connus)
    _pistes_locales(mots, connus, pistes)
    classes = sorted(pistes.values(), key=lambda fiche: fiche["poids"], reverse=True)[:12]
    collecte._poser(total=len(classes) or 1, fait=0, message="Recherche des flux RSS")
    if not classes:
        collecte.liberer("Radar terminé · aucun site nouveau pour cette veille")
        return
    avant = {fiche["url"] for fiche in magasin.candidats(profil_id)}

    def un_site(cible: dict[str, Any]) -> dict[str, Any] | None:
        adresse = cible["direct"] or cible.get("page") or f"https://{cible['hote']}"
        pourquoi = cible["pourquoi"][0] if cible["pourquoi"] else cible["hote"]
        try:
            fiche = examiner(adresse, profil_id, mots, pourquoi)
        except Exception:
            fiche = {"erreur": cible["hote"]}
        with collecte.job_lock:
            collecte.job["fait"] += 1
            collecte.job["message"] = f"Flux {collecte.job['fait']} / {collecte.job['total']} · {cible['nom']}"
        if "url" not in fiche or int(fiche.get("score") or 0) < 2:
            return None
        return fiche

    with ThreadPoolExecutor(max_workers=4) as pool:
        for fiche in pool.map(un_site, classes):
            if fiche:
                magasin.enregistrer_candidat(fiche)
    apres = magasin.candidats(profil_id)
    nouveaux = sum(1 for fiche in apres if fiche["url"] not in avant)
    collecte.liberer(f"Radar terminé · {nouveaux} nouveau(x) flux · {len(apres)} en attente")


def demarrer_radar(profil_id: str) -> bool:
    if not collecte.occuper("radar", "Radar des nouvelles sources"):
        return False
    threading.Thread(target=_radar, args=(profil_id,), daemon=True).start()
    return True


def adopter(url: str) -> dict[str, Any]:
    fiche = magasin.decider_candidat(url, "ajoute")
    if fiche is None:
        return {"erreur": "Candidat introuvable."}
    identifiant = "dec-" + _slug(hote(url))
    magasin.enregistrer_source(
        {
            "id": identifiant,
            "nom": fiche["nom"],
            "url": fiche["url"],
            "site": fiche["site"],
            "kind": "flux",
            "filtre": "mots_cles",
            "profils": [],
        }
    )
    source = magasin.source_par_url(fiche["url"])
    if source:
        collecte.lire_source(source)
    return {"ok": True, "nom": fiche["nom"]}
