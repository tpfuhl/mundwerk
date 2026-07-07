# Mundwerk — Server

Django/DRF-Backend mit Parselmouth-Analysepipeline. Siehe `../PLAN.md`
für den Gesamtplan, `validation/README.md` für die Offline-Validierung.

## Struktur

```
server/
├── config/       Django-Settings, URLs
├── api/          DRF-App: Item, TargetSegment, Recording + Endpoints
├── analysis/     framework-freie Pipeline (Parselmouth) + Referenzwerte
│                 → wird von api/ UND validation/ benutzt
├── validation/   Phase-0-Skripte (validate.py, Testvokal-Synthese)
└── manage.py
```

## Setup & Start

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python manage.py migrate        # legt DB an, seedet Referenzwerte + Items
.venv/bin/python manage.py runserver
```

Admin-Zugang (zum Kuratieren der Referenzwerte und Items):
`.venv/bin/python manage.py createsuperuser`, dann http://127.0.0.1:8000/admin/

## API

```
GET  /api/items/?level=A1     Übungswörter
GET  /api/items/{id}/
POST /api/recordings/         multipart: item_id, speaker (male|female|child), audio (WAV mono)
                              → analysiert synchron, antwortet mit result
GET  /api/recordings/{id}/    Ergebnis erneut abrufen
```

Beispiel:

```bash
curl -X POST http://127.0.0.1:8000/api/recordings/ \
     -F item_id=2 -F speaker=male -F audio=@aufnahme.wav
```

Antwort (`result.segments[]`): pro Fokus-Phone `f1/f2` (gemessen),
`target_f1/f2`, `z_f1/z_f2`, `distanz`, `rating` (grün/gelb/rot),
`feedback` (artikulatorische Hinweise), `start/end` (Segment in s).

## Wortlisten pflegen (Kirsten)

Zwei Wege: einzeln im Django-Admin (Items), oder gesammelt per CSV:

```bash
.venv/bin/python manage.py import_items wortliste.csv --dry-run   # erst prüfen
.venv/bin/python manage.py import_items wortliste.csv
```

CSV-Spalten: `text, ipa, level, focus` (focus = Fokus-Laute in IPA,
mehrere durch Leerzeichen). Komma- oder Semikolon-getrennt (deutsches
Excel/LibreOffice funktioniert direkt). Vorhandene Wörter (gleicher
`text`) werden aktualisiert, nicht dupliziert. Vorlage:
`data/beispiel_wortliste.csv`. Der Import warnt, wenn ein Fokus-Laut
noch keine Referenzwerte (TargetSegment) hat.

## Stand / bewusste Vereinfachungen

- **Segmentierung:** ohne MFA wird der längste stimmhafte Abschnitt
  gemessen → Items sind vokal-dominante Einsilber. MFA-Integration
  (Forced Alignment für beliebige Wörter/Sätze) ist der nächste
  Serverschritt; die Analyse wandert dann in einen Celery-Task
  (POST → 202 + Polling).
- **Sprechernormalisierung:** nur male/female/child-Tabellen; Lobanov-
  Kalibrierung beim Onboarding kommt in Phase 1.
- **Auth:** Token-Pflicht auf allen Endpoints
  (`Authorization: Token <key>`). Tokens pro Nutzer anlegen im Admin
  (Auth Token → Tokens) oder per `manage.py drf_create_token <user>`.
  Die App liest ihren Token aus `local.properties`
  (`mundwerk.apiToken=…`). Offen bleibt: Löschkonzept für Aufnahmen
  (DSGVO).
- **Referenzwerte:** Literatur-Startwerte, per Seed-Migration in die DB
  übernommen und im Admin kuratierbar. `analysis/reference_formants.py`
  ist danach nur noch Fallback/Seed-Quelle.
- **Audio-Lebenszyklus:** hochgeladene Aufnahmen werden direkt nach der
  Analyse gelöscht (das Ergebnis-JSON bleibt). Ausnahme: User in der
  Gruppe „korpus“ (Einwilligung, z. B. Team) — deren Audio bleibt für
  die Referenzwert-Kalibrierung. Sicherheitsnetz per Cron:
  `manage.py prune_audio --days 30`. Jeder User sieht über die API nur
  seine eigenen Aufnahmen.
