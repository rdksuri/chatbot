import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from chatbot import app as appmod
from chatbot.suche import Index, tokens

CHUNKS = [
    {"id": "A#0", "titel": "Reiserichtlinie", "ueberschrift": "Spesen", "quelle": "https://sp/a",
     "geaendert_am": "2026-09-01T00:00:00Z", "text": "Für Dienstreisen gilt eine Spesenpauschale von 50 Euro pro Tag."},
    {"id": "B#0", "titel": "Urlaubsregelung", "ueberschrift": "", "quelle": "https://sp/b",
     "geaendert_am": "2026-08-01T00:00:00Z", "text": "Der Urlaubsanspruch beträgt 30 Tage im Jahr."},
    {"id": "C#0", "titel": "Prozess Beschaffung", "ueberschrift": "Bestellung", "quelle": "https://sp/c",
     "geaendert_am": None, "text": "Bestellungen über 1000 Euro benötigen eine Freigabe."},
]


def test_tokens_normalisiert():
    assert tokens("Die Beantragungen der Dienstreisen") == tokens("beantragung dienstreise")
    assert "ueber" not in tokens("über")  # Stoppwort


def test_suche_findet_passenden_abschnitt():
    idx = Index(CHUNKS)
    assert idx.suche("Wie viele Urlaubstage habe ich?")[0]["id"] == "B#0"
    assert idx.suche("Spesen bei Dienstreisen")[0]["id"] == "A#0"
    assert idx.suche("Quantenphysik") == []


class FakeStream:
    def __init__(self, kwargs):
        self.kwargs = kwargs
        self.text_stream = iter(["Es gilt eine ", "Pauschale von 50 Euro [1]."])

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def get_final_message(self):
        return SimpleNamespace(stop_reason="end_turn")


@pytest.fixture
def client(monkeypatch):
    aufrufe = []

    def stream(**kwargs):
        aufrufe.append(kwargs)
        return FakeStream(kwargs)

    fake = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(stream=stream)))
    monkeypatch.setattr(appmod, "_client", fake)
    monkeypatch.setattr(appmod.wissensbasis, "index", lambda: Index(CHUNKS))
    monkeypatch.setattr(appmod, "PASSWORT", None)
    return TestClient(appmod.app), aufrufe


def ereignisse(body: str):
    for block in body.strip().split("\n\n"):
        ev, daten = block.split("\n")
        yield ev.removeprefix("event: "), json.loads(daten.removeprefix("data: "))


def test_chat_streamt_quellen_und_text(client):
    tc, aufrufe = client
    r = tc.post("/api/chat", json={"nachrichten": [{"rolle": "nutzer", "text": "Wie hoch sind die Spesen?"}]})
    assert r.status_code == 200
    evs = list(ereignisse(r.text))
    assert evs[0][0] == "quellen" and evs[0][1][0]["url"] == "https://sp/a"
    assert "".join(d for e, d in evs if e == "text") == "Es gilt eine Pauschale von 50 Euro [1]."
    assert evs[-1][0] == "ende"
    gesendet = aufrufe[0]
    assert gesendet["model"] == "claude-opus-5-5"
    assert gesendet["fallbacks"] == "default"
    assert "<quellen>" in gesendet["messages"][-1]["content"]
    assert "Spesenpauschale" in gesendet["messages"][-1]["content"]


def test_verlauf_wird_uebergeben(client):
    tc, aufrufe = client
    tc.post("/api/chat", json={"nachrichten": [
        {"rolle": "nutzer", "text": "Wie viel Urlaub?"},
        {"rolle": "assistent", "text": "30 Tage [1]."},
        {"rolle": "nutzer", "text": "Und ab wann?"},
    ]})
    msgs = aufrufe[0]["messages"]
    assert [m["role"] for m in msgs] == ["user", "assistant", "user"]
    assert "Urlaubsanspruch" in msgs[-1]["content"]  # vorige Frage fliesst in die Suche ein


def test_passwortschutz(client, monkeypatch):
    tc, _ = client
    monkeypatch.setattr(appmod, "PASSWORT", "geheim")
    assert tc.get("/").status_code == 401
    assert tc.get("/", auth=("x", "geheim")).status_code == 200


def test_letzte_nachricht_muss_vom_nutzer_sein(client):
    tc, _ = client
    r = tc.post("/api/chat", json={"nachrichten": [{"rolle": "assistent", "text": "Hallo"}]})
    assert r.status_code == 422
