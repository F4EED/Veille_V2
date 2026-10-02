"""Veille vive : collecte unique, veilles et mots-clés immédiats."""

__version__ = "2.1.0"

from __future__ import annotations

import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
VENDOR_V1 = Path(r"C:\Apps\veille_techno\.vendor")
if VENDOR_V1.exists():
    sys.path.insert(0, str(VENDOR_V1))
