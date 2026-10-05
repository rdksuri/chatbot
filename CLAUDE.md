# Hinweise für Claude

Web-Chatbot über der Wissensbasis `rdksuri/wissensbasis`.

- Sprache: **Hochdeutsch**; Antworten des Bots immer mit Quellenangabe.
- Datenformat kommt aus `rdksuri/wissensbasis` → `docs/schnittstelle.md`
  (Schema-Version 1). Änderungen dort zuerst abstimmen.
- Keine Zugangsdaten ins Repo (Repo ist öffentlich); Konfiguration nur über
  Umgebungsvariablen, siehe `.env.beispiel`.
- Nach Änderungen: `python -m pytest -q`.
