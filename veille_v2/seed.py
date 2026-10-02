"""Importe le catalogue et les mots-clés de veille_techno, une seule fois."""

from __future__ import annotations

import json
import re
import urllib.parse
from pathlib import Path
from typing import Any

import yaml

from veille_v2 import magasin

V1 = Path(r"C:\Apps\veille_techno\config")

PROFILS = (
    ("iot", "IoT", "Objets connectés, LoRa, mesh, routes, radio.", 7, "keywords.yaml"),
    ("crise", "Crise", "Risques, alertes, aléas, gestion de crise.", 7, "keywords_crise.yaml"),
    ("radio", "Radio", "Radioamateur, modes digitaux, SDR, trafic.", 7, "keywords_radio.yaml"),
    ("outils", "Outils PC", "Logiciels de crise et poste de commandement.", 7, "keywords_outils.yaml"),
    ("blackout", "Black-out", "Réseau électrique, délestage, résilience.", 14, "keywords_blackout.yaml"),
    ("geomatique", "Géomatique", "QGIS, cartographie, lidar, données géographiques.", 7, "keywords_geomatique.yaml"),
    ("mesh", "Mesh", "Meshtastic, MeshCore, firmwares et mesh Wi-Fi.", 7, "keywords_mesh.yaml"),
)


def _charger(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _slug(texte: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", texte.lower()).strip("-") or "source"


def url_google_news(query: str, hl: str, gl: str, ceid: str) -> str:
    params = urllib.parse.urlencode({"q": query, "hl": hl, "gl": gl, "ceid": ceid})
    return f"https://news.google.com/rss/search?{params}"


def _requete_site(sites: list[str], query: str) -> str:
    if len(sites) == 1:
        return f"site:{sites[0]} ({query})"
    clause = " OR ".join(f"site:{site}" for site in sites)
    return f"({clause}) ({query})"


HCFRN = {
    "id": "hcfrn",
    "nom": "HCFRN",
    "url": "https://www.hcfrn.org/blog-feed.xml",
    "site": "https://www.hcfrn.org/",
    "kind": "flux",
    "filtre": "mots_cles",
}


def _complements() -> None:
    """Sources ajoutées après le premier import, et carnet d'envoi initial."""
    if magasin.source_par_url(HCFRN["url"]) is None:
        magasin.enregistrer_source(HCFRN)
    if magasin.meta("courriel") == "1":
        return
    cfg = _charger(V1 / "email.yaml")
    identifiants = [fiche["id"] for fiche in magasin.profils()]
    connus = {fiche["id"] for fiche in magasin.profils()}
    for adresse in cfg.get("destinataires") or []:
        if str(adresse).strip():
            magasin.enregistrer_courriel(str(adresse), identifiants)
    for profil, adresses in (cfg.get("destinataires_profils") or {}).items():
        if profil not in connus:
            continue
        deja = {ligne["email"]: list(ligne["profils"]) for ligne in magasin.courriels()}
        for adresse in adresses or []:
            if not str(adresse).strip():
                continue
            cle = str(adresse).strip().lower()
            profils = deja.get(cle, [])
            if profil not in profils:
                profils.append(profil)
            magasin.enregistrer_courriel(cle, profils)
            deja[cle] = profils
    magasin.ecrire_meta("courriel", "1")


def assurer() -> dict[str, int]:
    magasin.initialiser()
    if magasin.meta("seed") == "1":
        _complements()
        return {"deja": 1}
    if not (V1 / "sources.yaml").exists():
        magasin.ecrire_meta("seed", "1")
        _complements()
        return {"sans_v1": 1}

    sources = _charger(V1 / "sources.yaml")
    reseaux = _charger(V1 / "reseaux_sociaux.yaml")
    with magasin.connecter() as conn:
        for identifiant, titre, perimetre, jours, fichier in PROFILS:
            cfg = _charger(V1 / fichier)
            conn.execute(
                "INSERT OR IGNORE INTO profils(id, titre, perimetre, periode_jours) VALUES(?, ?, ?, ?)",
                (identifiant, titre, perimetre, int(cfg.get("periode_jours") or jours)),
            )
            for did, data in (cfg.get("domaines") or {}).items():
                conn.execute(
                    "INSERT OR IGNORE INTO domaines(profil_id, id, label, priorite) VALUES(?, ?, ?, ?)",
                    (identifiant, did, data.get("label") or did, int(data.get("priorite") or 0)),
                )
                for mot in data.get("mots_cles") or []:
                    if str(mot).strip():
                        conn.execute(
                            """
                            INSERT OR IGNORE INTO mots(profil_id, genre, domaine_id, tendance_id, brut)
                            VALUES(?, 'domaine', ?, '', ?)
                            """,
                            (identifiant, did, str(mot).strip()),
                        )
            for tendance in cfg.get("tendances") or []:
                tid = str(tendance.get("id") or "")
                if not tid:
                    continue
                conn.execute(
                    "INSERT OR IGNORE INTO tendances(profil_id, id, label) VALUES(?, ?, ?)",
                    (identifiant, tid, tendance.get("label") or tid),
                )
                for mot in tendance.get("mots_cles") or []:
                    if str(mot).strip():
                        conn.execute(
                            """
                            INSERT OR IGNORE INTO mots(profil_id, genre, domaine_id, tendance_id, brut)
                            VALUES(?, 'tendance', '', ?, ?)
                            """,
                            (identifiant, tid, str(mot).strip()),
                        )

        vus: set[str] = set()

        def ajouter(fiche: dict[str, Any]) -> None:
            url = fiche["url"].strip()
            if not url or url in vus:
                return
            vus.add(url)
            identifiant = fiche["id"]
            pris = {row[0] for row in conn.execute("SELECT id FROM sources")}
            if identifiant in pris:
                n = 2
                while f"{identifiant}-{n}" in pris:
                    n += 1
                identifiant = f"{identifiant}-{n}"
            conn.execute(
                """
                INSERT OR IGNORE INTO sources(
                    id, nom, url, site, kind, filtre, domaine, profils, ignorer_date, actif, requete
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    identifiant,
                    fiche["nom"],
                    url,
                    fiche.get("site") or "",
                    fiche["kind"],
                    fiche.get("filtre") or "mots_cles",
                    fiche.get("domaine") or "",
                    json.dumps(list(fiche.get("profils") or []), ensure_ascii=False),
                    1 if fiche.get("ignorer_date") else 0,
                    0 if fiche["kind"] == "wms" else 1,
                    fiche.get("requete") or "",
                ),
            )

        for item in sources.get("google_news") or []:
            ajouter(
                {
                    "id": item["id"],
                    "nom": item.get("label") or item["id"],
                    "url": url_google_news(
                        item["query"], item.get("hl", "fr"), item.get("gl", "FR"), item.get("ceid", "FR:fr")
                    ),
                    "site": item.get("site") or "https://news.google.com/",
                    "kind": "google_news",
                    "filtre": item.get("filtre") or "aucun",
                    "domaine": item.get("domaine") or "",
                    "profils": item.get("profils") or [],
                    "ignorer_date": True,
                    "requete": item.get("query") or "",
                }
            )
        for item in sources.get("flux") or []:
            ajouter(
                {
                    "id": item["id"],
                    "nom": item.get("nom") or item["id"],
                    "url": item["url"],
                    "site": item.get("site") or "",
                    "kind": "flux",
                    "filtre": item.get("filtre") or "mots_cles",
                    "domaine": item.get("domaine") or "",
                    "profils": item.get("profils") or [],
                    "ignorer_date": bool(item.get("ignorer_date")),
                }
            )
        for item in sources.get("wms") or []:
            ajouter(
                {
                    "id": item.get("id") or _slug(item.get("nom") or "wms"),
                    "nom": item.get("nom") or "WMS",
                    "url": item["url"],
                    "site": item.get("site") or "",
                    "kind": "wms",
                    "filtre": "aucun",
                }
            )

        liste_reseaux = list(reseaux.get("reseaux") or [])
        for req in sources.get("requetes_rs") or []:
            autorises = {str(x).lower() for x in (req.get("reseaux") or [])}
            for reseau in liste_reseaux:
                if autorises and str(reseau.get("id") or "").lower() not in autorises:
                    continue
                sites = list(reseau.get("sites") or [])
                if not sites or not req.get("query"):
                    continue
                rid = req.get("id") or _slug(str(req.get("label") or "rs"))
                ajouter(
                    {
                        "id": f"rs-{reseau['id']}-{rid}",
                        "nom": f"{reseau.get('label') or reseau['id']} — {req.get('label') or rid}",
                        "url": url_google_news(
                            _requete_site(sites, req["query"]),
                            req.get("hl", "fr"),
                            req.get("gl", "FR"),
                            req.get("ceid", "FR:fr"),
                        ),
                        "site": reseau.get("url") or f"https://{sites[0]}/",
                        "kind": "reseau",
                        "filtre": req.get("filtre") or "mots_cles",
                        "domaine": req.get("domaine") or "",
                        "profils": req.get("profils") or [],
                        "ignorer_date": True,
                        "requete": req.get("query") or "",
                    }
                )
        for tag in sources.get("mastodon_tags") or []:
            slug = _slug(str(tag))
            for instance in reseaux.get("mastodon_instances") or []:
                parse = urllib.parse.urlparse(instance if "://" in str(instance) else f"https://{instance}")
                base = f"{parse.scheme}://{parse.netloc}".rstrip("/")
                ajouter(
                    {
                        "id": f"masto-{_slug(parse.netloc)}-{slug}",
                        "nom": f"Mastodon #{tag} ({parse.netloc})",
                        "url": f"{base}/tags/{urllib.parse.quote(str(tag))}.rss",
                        "site": f"{base}/tags/{tag}",
                        "kind": "mastodon",
                        "filtre": "mots_cles",
                    }
                )

    magasin.ecrire_meta("seed", "1")
    magasin.toucher()
    _complements()
    stats = magasin.stats_sources()
    return {"profils": len(PROFILS), **stats}
