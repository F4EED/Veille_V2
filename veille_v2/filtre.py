"""Filtre une veille sur les articles déjà en base. Aucun téléchargement."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from veille_v2 import magasin
from veille_v2.texte import Mot, compiler, mots_trouves, normaliser

DATE_MIN = "2025-01-01T00:00:00+00:00"

_cache: dict[str, Any] = {"generation": -1, "profils": {}}


def _compiler_profil(profil_id: str) -> dict[str, Any]:
    mots = magasin.mots_de(profil_id)
    par_domaine: dict[str, list[Mot]] = {}
    par_tendance: dict[str, list[Mot]] = {}
    for ligne in mots:
        mot = compiler(ligne["brut"])
        if mot is None:
            continue
        if ligne["genre"] == "domaine":
            par_domaine.setdefault(ligne["domaine_id"], []).append(mot)
        else:
            par_tendance.setdefault(ligne["tendance_id"], []).append(mot)
    domaines_compiles = []
    for domaine in magasin.domaines(profil_id):
        domaines_compiles.append(
            {
                "id": domaine["id"],
                "label": domaine["label"],
                "priorite": domaine["priorite"],
                "mots": par_domaine.get(domaine["id"], []),
            }
        )
    tendances = []
    for tendance in magasin.tendances(profil_id):
        tendances.append(
            {
                "id": tendance["id"],
                "label": tendance["label"],
                "mots": par_tendance.get(tendance["id"], []),
            }
        )
    return {"domaines": domaines_compiles, "tendances": tendances, "ids": {d["id"] for d in domaines_compiles}}


def modele(profil_id: str) -> dict[str, Any]:
    gen = magasin.generation()
    if _cache["generation"] != gen:
        _cache["generation"] = gen
        _cache["profils"] = {}
    if profil_id not in _cache["profils"]:
        _cache["profils"][profil_id] = _compiler_profil(profil_id)
    return _cache["profils"][profil_id]


def invalider() -> None:
    _cache["generation"] = -1
    _cache["profils"] = {}


def _filtre_effectif(row: Any, profil_id: str, ids: set[str]) -> str:
    try:
        profils = json.loads(row["profils"] or "[]")
    except json.JSONDecodeError:
        profils = []
    if profils and profil_id not in profils:
        return "mots_cles"
    domaine = row["domaine"] or ""
    if domaine and domaine not in ids and (row["filtre"] or "") != "mots_cles":
        return "mots_cles"
    return row["filtre"] or "mots_cles"


def classer(texte: str, row: Any, profil_id: str, modele_profil: dict[str, Any]) -> dict[str, Any] | None:
    ids = modele_profil["ids"]
    domaines_ok: list[tuple[int, str, list[str]]] = []
    for domaine in modele_profil["domaines"]:
        hits = mots_trouves(texte, domaine["mots"])
        if hits:
            domaines_ok.append((domaine["priorite"], domaine["id"], hits))
    domaines_ok.sort(reverse=True)
    identifiants = [identifiant for _, identifiant, _ in domaines_ok]
    mots: list[str] = []
    vus: set[str] = set()
    for _, _, hits in domaines_ok:
        for mot in hits:
            cle = mot.lower()
            if cle not in vus:
                vus.add(cle)
                mots.append(mot)

    try:
        profils = json.loads(row["profils"] or "[]")
    except json.JSONDecodeError:
        profils = []
    domaine_source = row["domaine"] or ""
    if (not profils or profil_id in profils) and domaine_source in ids and domaine_source not in identifiants:
        identifiants.insert(0, domaine_source)

    if not identifiants and _filtre_effectif(row, profil_id, ids) != "aucun":
        return None

    tendances = [
        tendance["id"]
        for tendance in modele_profil["tendances"]
        if mots_trouves(texte, tendance["mots"])
    ]
    return {"domaines": identifiants, "mots": mots[:8], "tendances": tendances}


def essayer(profil_id: str, mot_brut: str, jours: int) -> dict[str, Any]:
    mot = compiler(mot_brut)
    if mot is None:
        return {"nombre": 0, "exemples": []}
    depuis = (datetime.now(timezone.utc) - timedelta(days=jours)).isoformat()
    depuis = max(depuis, DATE_MIN)
    exemples = []
    nombre = 0
    for row in magasin.articles_depuis(depuis):
        if not mot.present(row["texte_norm"]):
            continue
        nombre += 1
        if len(exemples) < 6:
            exemples.append(
                {
                    "titre": row["titre"],
                    "source": row["source_nom"],
                    "date": row["date_pub"],
                    "lien": row["lien"],
                }
            )
    return {"nombre": nombre, "exemples": exemples}


def lister(profil_id: str, jours: int, domaine: str = "", q: str = "", limite: int = 180, resume_max: int = 320) -> dict[str, Any]:
    fiche = magasin.profil(profil_id)
    if fiche is None:
        return {"total": 0, "rubriques": [], "articles": []}
    modele_profil = modele(profil_id)
    labels = {d["id"]: d["label"] for d in modele_profil["domaines"]}
    labels_tendance = {t["id"]: t["label"] for t in modele_profil["tendances"]}
    depuis = (datetime.now(timezone.utc) - timedelta(days=max(1, jours))).isoformat()
    depuis = max(depuis, DATE_MIN)
    recherche = compiler(q) if q.strip() else None
    comptes: dict[str, int] = {d["id"]: 0 for d in modele_profil["domaines"]}
    comptes[""] = 0
    retenus: list[dict[str, Any]] = []
    for row in magasin.articles_depuis(depuis):
        if recherche and not recherche.present(row["texte_norm"]):
            continue
        classe = classer(row["texte_norm"], row, profil_id, modele_profil)
        if classe is None:
            continue
        premier = classe["domaines"][0] if classe["domaines"] else ""
        comptes[premier] = comptes.get(premier, 0) + 1
        if domaine and premier != domaine:
            continue
        retenus.append(
            {
                "titre": row["titre"],
                "lien": row["lien"],
                "source": row["source_nom"],
                "date": row["date_pub"],
                "resume": (row["resume"] or "")[:resume_max],
                "domaine": premier,
                "domaine_label": labels.get(premier, "Sans rubrique"),
                "mots": classe["mots"],
                "tendances": [labels_tendance[t] for t in classe["tendances"] if t in labels_tendance],
                "_date": row["date_pub"] or "",
            }
        )
    retenus.sort(key=lambda article: article["_date"], reverse=True)
    for article in retenus:
        article.pop("_date", None)
    rubriques = [
        {"id": d["id"], "label": d["label"], "nombre": comptes.get(d["id"], 0)}
        for d in modele_profil["domaines"]
    ]
    if comptes.get("", 0):
        rubriques.append({"id": "", "label": "Sans rubrique", "nombre": comptes[""]})
    return {
        "total": sum(comptes.values()),
        "affiches": min(limite, len(retenus)),
        "rubriques": rubriques,
        "articles": retenus[:limite],
        "periode_jours": jours,
    }


def synthese(profil_id: str, jours: int) -> dict[str, Any]:
    """Comptes par rubrique et par mot-clé, pour la vue de synthèse."""
    fiche = magasin.profil(profil_id)
    if fiche is None:
        return {"titre": "", "total": 0, "rubriques": []}
    modele_profil = modele(profil_id)
    depuis = (datetime.now(timezone.utc) - timedelta(days=max(1, jours))).isoformat()
    depuis = max(depuis, DATE_MIN)
    comptes = {domaine["id"]: 0 for domaine in modele_profil["domaines"]}
    par_mot: dict[str, int] = {}
    extraits: dict[str, list[dict[str, str]]] = {}
    total = 0
    for row in magasin.articles_depuis(depuis):
        classe = classer(row["texte_norm"], row, profil_id, modele_profil)
        if classe is None:
            continue
        total += 1
        premier = classe["domaines"][0] if classe["domaines"] else ""
        if premier in comptes:
            comptes[premier] += 1
        for mot in classe["mots"]:
            cle = normaliser(mot)
            par_mot[cle] = par_mot.get(cle, 0) + 1
            extraits.setdefault(cle, []).append(
                {
                    "titre": row["titre"],
                    "resume": (row["resume"] or "").strip(),
                    "lien": row["lien"],
                    "source": row["source_nom"],
                    "date": row["date_pub"] or "",
                }
            )
    rubriques = []
    for domaine in modele_profil["domaines"]:
        trouves = []
        for mot in domaine["mots"]:
            nombre = par_mot.get(mot.normalise, 0)
            if nombre:
                articles = sorted(extraits.get(mot.normalise, []), key=lambda article: article["date"], reverse=True)
                vus: set[str] = set()
                uniques = []
                for article in articles:
                    cle_article = article["lien"] or article["titre"]
                    if cle_article in vus:
                        continue
                    vus.add(cle_article)
                    resume = article["resume"]
                    if len(resume) > 280:
                        resume = resume[:277].rsplit(" ", 1)[0] + "…"
                    uniques.append({**article, "resume": resume})
                    if len(uniques) == 8:
                        break
                trouves.append({"mot": mot.brut, "nombre": nombre, "articles": uniques})
        trouves.sort(key=lambda ligne: (-ligne["nombre"], ligne["mot"].lower()))
        if not trouves:
            trouves = [{"mot": mot.brut, "nombre": 0} for mot in domaine["mots"][:6]]
        rubriques.append(
            {
                "id": domaine["id"],
                "label": domaine["label"],
                "nombre": comptes.get(domaine["id"], 0),
                "mots": trouves[:10],
                "mots_total": len(domaine["mots"]),
            }
        )
    return {
        "titre": fiche["titre"],
        "total": total,
        "periode_jours": max(1, jours),
        "rubriques": rubriques,
    }
