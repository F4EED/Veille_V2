"""Normalisation et correspondance des mots-clés."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


def sans_accents(texte: str) -> str:
    decompose = unicodedata.normalize("NFD", texte)
    return "".join(ch for ch in decompose if unicodedata.category(ch) != "Mn")


def normaliser(texte: str) -> str:
    return re.sub(r"\s+", " ", sans_accents(texte or "").lower()).strip()


@dataclass(frozen=True)
class Mot:
    brut: str
    normalise: str
    motif: re.Pattern[str] | None

    def present(self, texte: str) -> bool:
        if self.motif is None:
            return self.normalise in texte
        return self.motif.search(texte) is not None


def compiler(brut: str) -> Mot | None:
    normalise = normaliser(brut)
    if not normalise:
        return None
    phrase = " " in normalise or "-" in normalise
    motif = None if phrase else re.compile(rf"(?<![a-z0-9]){re.escape(normalise)}(?![a-z0-9])")
    return Mot(brut=brut.strip(), normalise=normalise, motif=motif)


def mots_trouves(texte: str, mots: list[Mot]) -> list[str]:
    vus: set[str] = set()
    hits: list[str] = []
    for mot in mots:
        if not mot.present(texte):
            continue
        cle = mot.normalise
        if cle in vus:
            continue
        vus.add(cle)
        hits.append(mot.brut)
    return hits
