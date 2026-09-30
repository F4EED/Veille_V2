"""Console locale."""

from __future__ import annotations

import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from veille_v2 import collecte, decouverte, export, filtre, magasin
from veille_v2.seed import assurer

WEB = Path(__file__).resolve().parent.parent / "web"
HOTE = "127.0.0.1"
PORT = 8770


def _slug(texte: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", texte.lower()).strip("-")


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args) -> None:
        print("%s - %s" % (self.address_string(), fmt % args), flush=True)

    def _json(self, code: int, payload: dict) -> None:
        corps = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(corps)))
        self.end_headers()
        self.wfile.write(corps)

    def _fichier(self, nom: str, ctype: str) -> None:
        chemin = WEB / nom
        if not chemin.is_file():
            self._json(404, {"erreur": "Introuvable."})
            return
        corps = chemin.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(corps)))
        self.end_headers()
        self.wfile.write(corps)

    def _lire(self) -> dict:
        longueur = int(self.headers.get("Content-Length") or 0)
        if longueur <= 0:
            return {}
        brut = self.rfile.read(longueur)
        if not brut:
            return {}
        return json.loads(brut.decode("utf-8"))

    def do_GET(self) -> None:
        try:
            self._get()
        except Exception as exc:  # noqa: BLE001
            self._json(500, {"erreur": str(exc)})

    def do_POST(self) -> None:
        try:
            self._post()
        except Exception as exc:  # noqa: BLE001
            self._json(500, {"erreur": str(exc)})

    def _get(self) -> None:
        parse = urlparse(self.path)
        chemin = unquote(parse.path)
        qs = parse_qs(parse.query)
        if chemin in ("/", "/index.html"):
            self._fichier("index.html", "text/html; charset=utf-8")
            return
        if chemin == "/style.css":
            self._fichier("style.css", "text/css; charset=utf-8")
            return
        if chemin == "/app.js":
            self._fichier("app.js", "text/javascript; charset=utf-8")
            return
        if chemin == "/api/etat":
            self._json(200, {**magasin.stats_sources(), "job": collecte.etat_job()})
            return
        if chemin == "/api/profils":
            self._json(200, {"profils": magasin.profils()})
            return
        if chemin == "/api/articles":
            profil = (qs.get("profil") or ["iot"])[0]
            jours = int((qs.get("jours") or ["7"])[0])
            domaine = (qs.get("domaine") or [""])[0]
            q = (qs.get("q") or [""])[0]
            self._json(200, filtre.lister(profil, jours, domaine, q))
            return
        if chemin == "/api/synthese":
            profil = (qs.get("profil") or [""])[0]
            jours = int((qs.get("jours") or ["7"])[0])
            self._json(200, filtre.synthese(profil, jours))
            return
        if chemin == "/api/mots":
            profil = (qs.get("profil") or [""])[0]
            self._json(200, _vue_mots(profil))
            return
        if chemin == "/api/sources":
            self._json(200, {"sources": magasin.liste_sources(2000)})
            return
        if chemin == "/api/candidats":
            profil = (qs.get("profil") or [""])[0]
            self._json(200, {"candidats": magasin.candidats(profil)})
            return
        self._json(404, {"erreur": "Introuvable."})

    def _post(self) -> None:
        parse = urlparse(self.path)
        chemin = unquote(parse.path)
        corps = self._lire()
        if chemin == "/api/collecte":
            plafond = corps.get("plafond")
            if not collecte.demarrer(int(plafond) if plafond else None):
                self._json(409, {"erreur": "Une tâche est déjà en cours."})
                return
            self._json(202, {"ok": True})
            return
        if chemin == "/api/mots":
            profil = str(corps.get("profil") or "")
            domaine = str(corps.get("domaine") or "")
            mot = str(corps.get("mot") or "").strip()
            if not profil or not domaine or not mot:
                self._json(400, {"erreur": "Veille, rubrique et mot sont requis."})
                return
            magasin.ajouter_mot(profil, domaine, mot)
            filtre.invalider()
            self._json(200, _vue_mots(profil))
            return
        if chemin == "/api/mots/retirer":
            magasin.retirer_mot(str(corps.get("profil") or ""), str(corps.get("domaine") or ""), str(corps.get("mot") or ""))
            filtre.invalider()
            self._json(200, {"ok": True})
            return
        if chemin == "/api/essayer":
            self._json(
                200,
                filtre.essayer(str(corps.get("profil") or ""), str(corps.get("mot") or ""), int(corps.get("jours") or 7)),
            )
            return
        if chemin == "/api/chercher":
            resultat = decouverte.chercher_mot(
                str(corps.get("profil") or ""),
                str(corps.get("mot") or ""),
                str(corps.get("domaine") or ""),
            )
            code = 400 if resultat.get("erreur") and not resultat.get("ajoutees") else 200
            self._json(code, resultat)
            return
        if chemin == "/api/sonder":
            self._json(200, decouverte.sonder(str(corps.get("site") or ""), str(corps.get("profil") or "")))
            return
        if chemin == "/api/radar":
            if not decouverte.demarrer_radar(str(corps.get("profil") or "")):
                self._json(409, {"erreur": "Une tâche est déjà en cours."})
                return
            self._json(202, {"ok": True})
            return
        if chemin == "/api/adopter":
            self._json(200, decouverte.adopter(str(corps.get("url") or "")))
            return
        if chemin == "/api/rejeter":
            magasin.decider_candidat(str(corps.get("url") or ""), "rejete")
            self._json(200, {"ok": True})
            return
        if chemin == "/api/profils":
            titre = str(corps.get("titre") or "").strip()
            if len(titre) < 2:
                self._json(400, {"erreur": "Donne un nom à la veille."})
                return
            identifiant = _slug(titre)
            if magasin.profil(identifiant):
                self._json(400, {"erreur": "Cette veille existe déjà."})
                return
            magasin.creer_profil(identifiant, titre, str(corps.get("perimetre") or ""))
            self._json(200, {"id": identifiant})
            return
        if chemin == "/api/periode":
            magasin.definir_periode(str(corps.get("profil") or ""), int(corps.get("jours") or 7))
            self._json(200, {"ok": True})
            return
        if chemin == "/api/publier":
            try:
                resultat = export.publier(
                    str(corps.get("profil") or ""),
                    int(corps.get("jours") or 7),
                    str(corps.get("format") or ""),
                )
            except (ValueError, FileNotFoundError, RuntimeError, OSError) as exc:
                self._json(400, {"erreur": str(exc)})
                return
            self._json(200, resultat)
            return
        if chemin == "/api/publier-tout":
            if not export.demarrer_toutes():
                self._json(409, {"erreur": "Une tâche est déjà en cours."})
                return
            self._json(202, {"ok": True, "index": "https://f4eed.pages-perso.free.fr/Veille_2/"})
            return
        self._json(404, {"erreur": "Introuvable."})


def _vue_mots(profil_id: str) -> dict:
    mots = magasin.mots_de(profil_id)
    domaines = []
    for domaine in magasin.domaines(profil_id):
        domaines.append(
            {
                **domaine,
                "mots": [m["brut"] for m in mots if m["genre"] == "domaine" and m["domaine_id"] == domaine["id"]],
            }
        )
    tendances = []
    for tendance in magasin.tendances(profil_id):
        tendances.append(
            {
                **tendance,
                "mots": [m["brut"] for m in mots if m["genre"] == "tendance" and m["tendance_id"] == tendance["id"]],
            }
        )
    fiche = magasin.profil(profil_id) or {}
    return {"profil": fiche, "domaines": domaines, "tendances": tendances}


def main() -> None:
    bilan = assurer()
    print(f"Catalogue : {bilan}", flush=True)
    serveur = ThreadingHTTPServer((HOTE, PORT), Handler)
    print(f"Veille vive : http://{HOTE}:{PORT}", flush=True)
    serveur.serve_forever()
