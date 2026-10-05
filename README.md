# Wissens-Chatbot

Web-Chatbot, der einfache Fragen zu den Dokumenten der
[Wissensbasis](https://github.com/rdksuri/wissensbasis) beantwortet – immer mit
Quellenangabe und Link auf das SharePoint-Original.

```
Frage ──▶ BM25-Suche in index/chunks.jsonl ──▶ beste Abschnitte + Frage ──▶ Claude ──▶ Antwort mit [1], [2] …
```

## Funktionsweise

1. **Daten:** Die App lädt `index/chunks.jsonl` aus dem Wissensbasis-Repo
   (Standard: Raw-URL des `main`-Branches) und lädt alle 15 Minuten neu. Format:
   [`docs/schnittstelle.md`](https://github.com/rdksuri/wissensbasis/blob/main/docs/schnittstelle.md).
2. **Suche:** Volltextsuche mit BM25, deutsche Normalisierung (Umlaute,
   Stoppwörter, einfache Endungen) und Teilwort-Treffer für Komposita
   („Urlaub“ findet „Urlaubsanspruch“).
3. **Antwort:** Die besten Abschnitte gehen als nummerierte Quellen an Claude.
   Claude antwortet nur auf dieser Grundlage, belegt Aussagen mit `[n]` und sagt
   offen, wenn die Wissensbasis keine Antwort enthält. Die Antwort wird
   live gestreamt; die Oberfläche verlinkt jede zitierte Quelle.

Weitere Merkmale: Gesprächsverlauf für Rückfragen, optionaler Passwortschutz,
Prompt-Caching des Systemprompts, automatischer Modell-Fallback bei
Ablehnungen (`fallbacks: "default"`).

## Starten

```bash
pip install -r requirements.txt
cp .env.beispiel .env              # ANTHROPIC_API_KEY und CHAT_PASSWORT eintragen
set -a; . ./.env; set +a
uvicorn chatbot.app:app --reload   # http://localhost:8000
```

Mit Docker:

```bash
docker build -t wissens-chatbot .
docker run -p 8000:8000 --env-file .env wissens-chatbot
```

## Konfiguration (Umgebungsvariablen)

| Variable | Standard | Bedeutung |
|---|---|---|
| `ANTHROPIC_API_KEY` | – | API-Schlüssel (https://console.anthropic.com) |
| `CHAT_PASSWORT` | leer | Passwort für HTTP-Basic-Anmeldung; **leer = öffentlich zugänglich** |
| `WISSENSBASIS_URL` | Raw-URL `rdksuri/wissensbasis` `main` | URL oder lokaler Pfad zu `chunks.jsonl` |
| `CLAUDE_MODELL` | `claude-opus-5-5` | Modell |
| `CLAUDE_EFFORT` | `low` | Denkaufwand (`low` … `max`); `low` = schnelle Chat-Antworten |
| `TREFFER` | `8` | Anzahl Abschnitte pro Frage |

**Hinweis:** Ohne `CHAT_PASSWORT` kann jeder, der die Adresse kennt, Fragen
stellen – und jede Frage verursacht API-Kosten.

## Entwicklung

```bash
pip install -r requirements-dev.txt
python -m pytest -q   # ohne API-Schlüssel, Claude wird simuliert
```

## Quellen

- Anthropic, *Messages API / Streaming*: <https://docs.claude.com/en/docs/build-with-claude/streaming>
- Anthropic, *Prompt Caching*: <https://docs.claude.com/en/docs/build-with-claude/prompt-caching>
- Anthropic, *Refusals and fallback*: <https://platform.claude.com/docs/en/build-with-claude/refusals-and-fallback>
- Robertson & Zaragoza (2009), *The Probabilistic Relevance Framework: BM25 and Beyond*: <https://doi.org/10.1561/1500000019>
- FastAPI: <https://fastapi.tiangolo.com>
