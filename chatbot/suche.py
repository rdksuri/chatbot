"""Lädt index/chunks.jsonl aus der Wissensbasis und durchsucht ihn per BM25.

BM25: Robertson & Zaragoza, "The Probabilistic Relevance Framework: BM25 and
Beyond" (2009), https://doi.org/10.1561/1500000019
"""

from __future__ import annotations

import json
import logging
import math
import os
import re
import threading
import time
import unicodedata
from collections import Counter
from pathlib import Path

import httpx

log = logging.getLogger(__name__)

_STOPPWOERTER = set("""
aber alle allem allen aller alles als also am an ander andere anderem anderen
anderer anderes auch auf aus bei bin bis bist da damit dann das dass dein deine
dem den der des dessen die dies diese diesem diesen dieser dieses doch dort du
durch ein eine einem einen einer eines er es etwas euch euer für gegen gibt hab
habe haben hat hatte hier hin ich ihm ihn ihnen ihr im in indem ins ist ja jede
jedem jeden jeder jedes kann kein keine können man manche mich mir mit muss
müssen nach nicht nichts noch nun nur ob oder ohne sehr sein seine sich sie sind
so solche soll sollen sondern um und uns unser unter viel vom von vor war waren
was weil welche welchem welchen welcher welches wenn wer werden wie wir wird
wo wurde zu zum zur über wann wieso warum weshalb bitte
""".split())


def _normalisiere(text: str) -> str:
    text = unicodedata.normalize("NFKC", text.lower())
    return text.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")


_STOPPWOERTER = {_normalisiere(w) for w in _STOPPWOERTER}


def tokens(text: str) -> list[str]:
    text = _normalisiere(text)
    woerter = re.findall(r"\w+", text)
    # einfache Grundformreduktion für gängige deutsche Endungen
    ergebnis = []
    for w in woerter:
        if w in _STOPPWOERTER or len(w) < 2:
            continue
        for endung in ("ungen", "heiten", "keiten", "ung", "en", "er", "es", "e", "n", "s"):
            if len(w) > len(endung) + 3 and w.endswith(endung):
                w = w[: -len(endung)]
                break
        ergebnis.append(w)
    return ergebnis


class Index:
    def __init__(self, chunks: list[dict], k1: float = 1.5, b: float = 0.75):
        self.chunks = chunks
        self.k1, self.b = k1, b
        self.dok_tokens = [
            Counter(tokens(f"{c.get('titel') or ''} {c.get('ueberschrift') or ''} {c['text']}"))
            for c in chunks
        ]
        self.laengen = [sum(t.values()) for t in self.dok_tokens]
        self.avg = (sum(self.laengen) / len(self.laengen)) if chunks else 0
        df = Counter()
        for t in self.dok_tokens:
            df.update(t.keys())
        n = len(chunks)
        self.idf = {w: math.log(1 + (n - f + 0.5) / (f + 0.5)) for w, f in df.items()}
        self._erweiterung: dict[str, list[tuple[str, float]]] = {}

    def _verwandte(self, wort: str) -> list[tuple[str, float]]:
        """Exakter Treffer (Gewicht 1) plus Komposita-Teiltreffer (Gewicht 0.5).

        Deutsche Zusammensetzungen wie "Urlaub"/"Urlaubsanspruch"/"Urlaubstage"
        teilen einen langen gemeinsamen Anfang; das genügt als Näherung.
        """
        if wort not in self._erweiterung:
            treffer = [(wort, 1.0)] if wort in self.idf else []
            if len(wort) >= 4:
                for v in self.idf:
                    if v == wort or len(v) < 4:
                        continue
                    gemeinsam = len(os.path.commonprefix([wort, v]))
                    if gemeinsam >= max(4, math.ceil(0.6 * min(len(wort), len(v)))):
                        treffer.append((v, 0.5))
            self._erweiterung[wort] = treffer
        return self._erweiterung[wort]

    def suche(self, frage: str, k: int = 8) -> list[dict]:
        q = tokens(frage)
        if not q or not self.chunks:
            return []
        begriffe = [b for w in q for b in self._verwandte(w)]
        werte = []
        for i, tf in enumerate(self.dok_tokens):
            s = 0.0
            for w, gewicht in begriffe:
                f = tf.get(w)
                if f:
                    s += gewicht * self.idf[w] * f * (self.k1 + 1) / (
                        f + self.k1 * (1 - self.b + self.b * self.laengen[i] / self.avg)
                    )
            if s > 0:
                werte.append((s, i))
        werte.sort(reverse=True)
        return [self.chunks[i] | {"score": round(s, 3)} for s, i in werte[:k]]


def lade_chunks(quelle: str) -> list[dict]:
    """quelle: lokaler Pfad oder http(s)-URL zu chunks.jsonl."""
    if quelle.startswith(("http://", "https://")):
        r = httpx.get(quelle, timeout=60, follow_redirects=True)
        r.raise_for_status()
        inhalt = r.text
    else:
        inhalt = Path(quelle).read_text(encoding="utf-8")
    return [json.loads(z) for z in inhalt.splitlines() if z.strip()]


class Wissensbasis:
    """Hält den Index im Speicher und lädt ihn regelmässig neu."""

    def __init__(self, quelle: str, neu_laden_sekunden: int = 900):
        self.quelle = quelle
        self.intervall = neu_laden_sekunden
        self._index = Index([])
        self._geladen = 0.0
        self._lock = threading.Lock()

    def index(self) -> Index:
        if time.time() - self._geladen > self.intervall:
            with self._lock:
                if time.time() - self._geladen > self.intervall:
                    try:
                        self._index = Index(lade_chunks(self.quelle))
                        log.info("Wissensbasis geladen: %d Abschnitte", len(self._index.chunks))
                    except Exception:  # noqa: BLE001 – alter Index bleibt nutzbar
                        log.exception("Wissensbasis konnte nicht geladen werden")
                    self._geladen = time.time()
        return self._index
