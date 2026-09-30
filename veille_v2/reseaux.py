"""Recherches Google News des mots-clés sur X, Instagram et Snap."""

from __future__ import annotations

import hashlib
import re

from veille_v2 import magasin
from veille_v2.seed import url_google_news
from veille_v2.texte import normaliser

RESEAUX = (
    ("x", "X", ("x.com", "twitter.com"), "https://x.com/"),
    ("instagram", "Instagram", ("instagram.com",), "https://www.instagram.com/"),
    ("snap", "Snap", ("snapchat.com",), "https://www.snapchat.com/"),
)
LANGUES = (
    ("fr", "FR", "FR:fr"),
    ("en", "US", "US:en"),
)
TAILLE_PAQUET = 8
BUDGET = 180


def _mots() -> list[str]:
    vus: set[str] = set()
    ordre: list[str] = []
    with magasin.connecter() as conn:
        rows = conn.execute(
            "SELECT brut FROM mots WHERE genre = 'domaine' ORDER BY brut"
        ).fetchall()
    for row in rows:
        mot = re.sub(r"""["'()]+""", " ", row["brut"] or "")
        mot = re.sub(r"\s+", " ", mot).strip()
        cle = normaliser(mot)
        if len(cle) < 3 or cle in vus:
            continue
        vus.add(cle)
        ordre.append(mot)
    ordre.sort(key=normaliser)
    return ordre


def _paquets(mots: list[str]) -> list[list[str]]:
    groupes: list[list[str]] = []
    courant: list[str] = []
    taille = 0
    for mot in mots:
        ajoute = len(mot) + 6
        if courant and (len(courant) >= TAILLE_PAQUET or taille + ajoute > BUDGET):
            groupes.append(courant)
            courant = []
            taille = 0
        courant.append(mot)
        taille += ajoute
    if courant:
        groupes.append(courant)
    return groupes


def _requete(sites: tuple[str, ...], mots: list[str]) -> str:
    termes = " OR ".join(f'"{mot}"' for mot in mots)
    if len(sites) == 1:
        return f"site:{sites[0]} ({termes})"
    sites_clause = " OR ".join(f"site:{site}" for site in sites)
    return f"({sites_clause}) ({termes})"


def synchroniser() -> int:
    """Active une recherche par paquet de mots-clés, pour chaque réseau et chaque langue."""
    fiches: list[tuple[str, str, str, str, str, str]] = []
    for identifiant, label, sites, page in RESEAUX:
        for paquet in _paquets(_mots()):
            requete = _requete(sites, paquet)
            apercu = ", ".join(paquet[:3])
            if len(paquet) > 3:
                apercu += "…"
            for hl, gl, ceid in LANGUES:
                url = url_google_news(requete, hl, gl, ceid)
                cle = hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]
                langue = "français" if hl == "fr" else "anglais"
                fiches.append(
                    (
                        f"rsoc-{identifiant}-{cle}",
                        f"{label} — {apercu} ({langue})",
                        url,
                        page,
                        requete,
                        identifiant,
                    )
                )
    with magasin.connecter() as conn:
        conn.execute("UPDATE sources SET actif = 0 WHERE id LIKE 'rsoc-%'")
        conn.executemany(
            """
            INSERT INTO sources(
                id, nom, url, site, kind, filtre, domaine, profils, ignorer_date, actif, requete
            ) VALUES(?, ?, ?, ?, 'reseau', 'mots_cles', '', '[]', 1, 1, ?)
            ON CONFLICT(url) DO UPDATE SET
                actif = 1,
                nom = excluded.nom,
                requete = excluded.requete,
                kind = 'reseau',
                filtre = 'mots_cles'
            """,
            [(ident, nom, url, site, requete) for ident, nom, url, site, requete, _reseau in fiches],
        )
    return len(fiches)
