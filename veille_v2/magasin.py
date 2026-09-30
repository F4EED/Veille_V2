"""SQLite : sources, articles, veilles et mots-clés."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

RACINE = Path(__file__).resolve().parent.parent
DATA = RACINE / "data"
FICHIER = DATA / "veille.sqlite"

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    cle TEXT PRIMARY KEY,
    valeur TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS profils (
    id TEXT PRIMARY KEY,
    titre TEXT NOT NULL,
    perimetre TEXT NOT NULL DEFAULT '',
    periode_jours INTEGER NOT NULL DEFAULT 7
);
CREATE TABLE IF NOT EXISTS domaines (
    profil_id TEXT NOT NULL,
    id TEXT NOT NULL,
    label TEXT NOT NULL,
    priorite INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (profil_id, id)
);
CREATE TABLE IF NOT EXISTS tendances (
    profil_id TEXT NOT NULL,
    id TEXT NOT NULL,
    label TEXT NOT NULL,
    PRIMARY KEY (profil_id, id)
);
CREATE TABLE IF NOT EXISTS mots (
    profil_id TEXT NOT NULL,
    genre TEXT NOT NULL,
    domaine_id TEXT NOT NULL DEFAULT '',
    tendance_id TEXT NOT NULL DEFAULT '',
    brut TEXT NOT NULL,
    PRIMARY KEY (profil_id, genre, domaine_id, tendance_id, brut)
);
CREATE TABLE IF NOT EXISTS sources (
    id TEXT PRIMARY KEY,
    nom TEXT NOT NULL,
    url TEXT NOT NULL UNIQUE,
    site TEXT NOT NULL DEFAULT '',
    kind TEXT NOT NULL,
    filtre TEXT NOT NULL DEFAULT 'mots_cles',
    domaine TEXT NOT NULL DEFAULT '',
    profils TEXT NOT NULL DEFAULT '[]',
    ignorer_date INTEGER NOT NULL DEFAULT 0,
    actif INTEGER NOT NULL DEFAULT 1,
    requete TEXT NOT NULL DEFAULT '',
    etag TEXT NOT NULL DEFAULT '',
    last_modified TEXT NOT NULL DEFAULT '',
    dernier_ok TEXT NOT NULL DEFAULT '',
    erreur TEXT NOT NULL DEFAULT '',
    duree_ms INTEGER NOT NULL DEFAULT 0,
    nb_entrees INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS articles (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    titre TEXT NOT NULL,
    lien TEXT NOT NULL DEFAULT '',
    resume TEXT NOT NULL DEFAULT '',
    date_pub TEXT,
    texte_norm TEXT NOT NULL,
    editeur_nom TEXT NOT NULL DEFAULT '',
    editeur_url TEXT NOT NULL DEFAULT '',
    recupere TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_articles_date ON articles(date_pub);
CREATE INDEX IF NOT EXISTS idx_articles_source ON articles(source_id);
CREATE TABLE IF NOT EXISTS candidats (
    url TEXT PRIMARY KEY,
    nom TEXT NOT NULL,
    site TEXT NOT NULL,
    profil_id TEXT NOT NULL,
    raison TEXT NOT NULL DEFAULT '',
    echantillon TEXT NOT NULL DEFAULT '[]',
    score INTEGER NOT NULL DEFAULT 0,
    statut TEXT NOT NULL DEFAULT 'propose'
);
"""


def connecter() -> sqlite3.Connection:
    DATA.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(FICHIER, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def initialiser() -> None:
    with connecter() as conn:
        conn.executescript(SCHEMA)


def meta(cle: str, defaut: str = "") -> str:
    with connecter() as conn:
        row = conn.execute("SELECT valeur FROM meta WHERE cle = ?", (cle,)).fetchone()
    return row["valeur"] if row else defaut


def ecrire_meta(cle: str, valeur: str) -> None:
    with connecter() as conn:
        conn.execute(
            "INSERT INTO meta(cle, valeur) VALUES(?, ?) ON CONFLICT(cle) DO UPDATE SET valeur = excluded.valeur",
            (cle, valeur),
        )


def generation() -> int:
    return int(meta("generation", "0") or "0")


def toucher() -> None:
    ecrire_meta("generation", str(generation() + 1))


_ORDRE = ("iot", "crise", "radio", "outils", "blackout", "geomatique", "mesh")


def profils() -> list[dict[str, Any]]:
    with connecter() as conn:
        rows = [dict(row) for row in conn.execute("SELECT * FROM profils").fetchall()]
    rows.sort(key=lambda fiche: _ORDRE.index(fiche["id"]) if fiche["id"] in _ORDRE else 50)
    return rows


def profil(identifiant: str) -> dict[str, Any] | None:
    with connecter() as conn:
        row = conn.execute("SELECT * FROM profils WHERE id = ?", (identifiant,)).fetchone()
    return dict(row) if row else None


def domaines(profil_id: str) -> list[dict[str, Any]]:
    with connecter() as conn:
        rows = conn.execute(
            "SELECT * FROM domaines WHERE profil_id = ? ORDER BY priorite DESC, label",
            (profil_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def tendances(profil_id: str) -> list[dict[str, Any]]:
    with connecter() as conn:
        rows = conn.execute(
            "SELECT * FROM tendances WHERE profil_id = ? ORDER BY label",
            (profil_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def mots_de(profil_id: str) -> list[dict[str, Any]]:
    with connecter() as conn:
        rows = conn.execute(
            "SELECT * FROM mots WHERE profil_id = ? ORDER BY brut",
            (profil_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def ajouter_mot(profil_id: str, domaine_id: str, brut: str) -> None:
    with connecter() as conn:
        conn.execute(
            """
            INSERT INTO mots(profil_id, genre, domaine_id, tendance_id, brut)
            VALUES(?, 'domaine', ?, '', ?)
            ON CONFLICT DO NOTHING
            """,
            (profil_id, domaine_id, brut.strip()),
        )
    toucher()


def retirer_mot(profil_id: str, domaine_id: str, brut: str) -> None:
    with connecter() as conn:
        conn.execute(
            """
            DELETE FROM mots
            WHERE profil_id = ? AND genre = 'domaine' AND domaine_id = ? AND brut = ?
            """,
            (profil_id, domaine_id, brut),
        )
    toucher()


def definir_periode(profil_id: str, jours: int) -> None:
    with connecter() as conn:
        conn.execute(
            "UPDATE profils SET periode_jours = ? WHERE id = ?",
            (max(1, min(jours, 90)), profil_id),
        )


def creer_profil(identifiant: str, titre: str, perimetre: str) -> None:
    with connecter() as conn:
        conn.execute(
            "INSERT INTO profils(id, titre, perimetre, periode_jours) VALUES(?, ?, ?, 7)",
            (identifiant, titre.strip(), perimetre.strip()),
        )
        conn.execute(
            "INSERT INTO domaines(profil_id, id, label, priorite) VALUES(?, 'general', 'Général', 50)",
            (identifiant,),
        )
    toucher()


def sources_actives() -> list[dict[str, Any]]:
    with connecter() as conn:
        rows = conn.execute(
            "SELECT * FROM sources WHERE actif = 1 AND kind != 'wms' ORDER BY nom"
        ).fetchall()
    return [dict(row) for row in rows]


def orienter_recherche(url: str, domaine: str, profil_id: str) -> None:
    with connecter() as conn:
        conn.execute(
            """
            UPDATE sources
            SET filtre = 'aucun', domaine = ?, profils = ?, kind = 'live', actif = 1
            WHERE url = ?
            """,
            (domaine, json.dumps([profil_id], ensure_ascii=False), url),
        )


def source_par_url(url: str) -> dict[str, Any] | None:
    with connecter() as conn:
        row = conn.execute("SELECT * FROM sources WHERE url = ?", (url,)).fetchone()
    return dict(row) if row else None


def enregistrer_source(fiche: dict[str, Any]) -> None:
    with connecter() as conn:
        conn.execute(
            """
            INSERT INTO sources(
                id, nom, url, site, kind, filtre, domaine, profils, ignorer_date, actif, requete
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(url) DO NOTHING
            """,
            (
                fiche["id"],
                fiche["nom"],
                fiche["url"],
                fiche.get("site") or "",
                fiche["kind"],
                fiche.get("filtre") or "mots_cles",
                fiche.get("domaine") or "",
                json.dumps(fiche.get("profils") or [], ensure_ascii=False),
                1 if fiche.get("ignorer_date") else 0,
                0 if fiche.get("kind") == "wms" else 1,
                fiche.get("requete") or "",
            ),
        )


def maj_source_fetch(
    source_id: str,
    *,
    etag: str,
    last_modified: str,
    dernier_ok: str,
    erreur: str,
    duree_ms: int,
    nb_entrees: int,
) -> None:
    with connecter() as conn:
        conn.execute(
            """
            UPDATE sources
            SET etag = ?, last_modified = ?, dernier_ok = ?, erreur = ?, duree_ms = ?, nb_entrees = ?
            WHERE id = ?
            """,
            (etag, last_modified, dernier_ok, erreur[:240], duree_ms, nb_entrees, source_id),
        )


def inserer_articles(lignes: list[tuple]) -> int:
    if not lignes:
        return 0
    with connecter() as conn:
        avant = conn.total_changes
        conn.executemany(
            """
            INSERT INTO articles(
                id, source_id, titre, lien, resume, date_pub, texte_norm,
                editeur_nom, editeur_url, recupere
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                titre = excluded.titre,
                resume = excluded.resume,
                date_pub = COALESCE(excluded.date_pub, articles.date_pub),
                texte_norm = excluded.texte_norm,
                editeur_nom = CASE WHEN excluded.editeur_nom != '' THEN excluded.editeur_nom ELSE articles.editeur_nom END,
                editeur_url = CASE WHEN excluded.editeur_url != '' THEN excluded.editeur_url ELSE articles.editeur_url END,
                recupere = excluded.recupere
            """,
            lignes,
        )
        return conn.total_changes - avant


def articles_depuis(iso_min: str) -> list[sqlite3.Row]:
    with connecter() as conn:
        return conn.execute(
            """
            SELECT a.id, a.titre, a.lien, a.resume, a.date_pub, a.texte_norm,
                   a.editeur_nom, a.editeur_url, a.recupere,
                   s.id AS source_id, s.nom AS source_nom, s.filtre, s.domaine,
                   s.profils, s.ignorer_date, s.kind, s.url AS source_url
            FROM articles a
            JOIN sources s ON s.id = a.source_id
            WHERE s.actif = 1
              AND (
                    (a.date_pub IS NOT NULL AND a.date_pub >= ?)
                 OR (a.date_pub IS NULL AND a.recupere >= ?)
                 OR (s.kind = 'live' AND a.recupere >= ?)
              )
            """,
            (iso_min, iso_min, iso_min),
        ).fetchall()


def hotes_connus() -> set[str]:
    from urllib.parse import urlparse

    hotes: set[str] = set()
    with connecter() as conn:
        rows = conn.execute("SELECT url, site FROM sources").fetchall()
    for row in rows:
        for valeur in (row["url"], row["site"]):
            if not valeur:
                continue
            hote = urlparse(valeur).netloc.lower()
            if hote.startswith("www."):
                hote = hote[4:]
            if hote:
                hotes.add(hote)
    return hotes


def stats_sources() -> dict[str, int]:
    with connecter() as conn:
        total = conn.execute("SELECT COUNT(*) AS n FROM sources WHERE kind != 'wms'").fetchone()["n"]
        ok = conn.execute(
            "SELECT COUNT(*) AS n FROM sources WHERE kind != 'wms' AND erreur = '' AND dernier_ok != ''"
        ).fetchone()["n"]
        erreurs = conn.execute(
            "SELECT COUNT(*) AS n FROM sources WHERE kind != 'wms' AND erreur != ''"
        ).fetchone()["n"]
        articles = conn.execute("SELECT COUNT(*) AS n FROM articles").fetchone()["n"]
        wms = conn.execute("SELECT COUNT(*) AS n FROM sources WHERE kind = 'wms'").fetchone()["n"]
    return {"sources": total, "sources_ok": ok, "sources_erreur": erreurs, "articles": articles, "wms": wms}


def liste_sources(limite: int = 400) -> list[dict[str, Any]]:
    with connecter() as conn:
        rows = conn.execute(
            """
            SELECT id, nom, url, site, kind, filtre, domaine, profils, erreur, dernier_ok, duree_ms, nb_entrees, actif
            FROM sources
            ORDER BY CASE WHEN erreur != '' THEN 0 ELSE 1 END, nom
            LIMIT ?
            """,
            (limite,),
        ).fetchall()
    return [dict(row) for row in rows]


def enregistrer_candidat(fiche: dict[str, Any]) -> None:
    with connecter() as conn:
        conn.execute(
            """
            INSERT INTO candidats(url, nom, site, profil_id, raison, echantillon, score, statut)
            VALUES(?, ?, ?, ?, ?, ?, ?, 'propose')
            ON CONFLICT(url) DO UPDATE SET
                nom = excluded.nom,
                raison = excluded.raison,
                echantillon = excluded.echantillon,
                score = excluded.score,
                profil_id = excluded.profil_id,
                statut = CASE WHEN candidats.statut = 'rejete' THEN candidats.statut ELSE 'propose' END
            """,
            (
                fiche["url"],
                fiche["nom"],
                fiche["site"],
                fiche["profil_id"],
                fiche.get("raison") or "",
                json.dumps(fiche.get("echantillon") or [], ensure_ascii=False),
                int(fiche.get("score") or 0),
            ),
        )


def candidats(profil_id: str) -> list[dict[str, Any]]:
    with connecter() as conn:
        rows = conn.execute(
            """
            SELECT * FROM candidats
            WHERE profil_id = ? AND statut = 'propose'
            ORDER BY score DESC, nom
            """,
            (profil_id,),
        ).fetchall()
    resultat = []
    for row in rows:
        fiche = dict(row)
        try:
            fiche["echantillon"] = json.loads(fiche["echantillon"] or "[]")
        except json.JSONDecodeError:
            fiche["echantillon"] = []
        resultat.append(fiche)
    return resultat


def decider_candidat(url: str, statut: str) -> dict[str, Any] | None:
    with connecter() as conn:
        row = conn.execute("SELECT * FROM candidats WHERE url = ?", (url,)).fetchone()
        if row is None:
            return None
        conn.execute("UPDATE candidats SET statut = ? WHERE url = ?", (statut, url))
    return dict(row)
