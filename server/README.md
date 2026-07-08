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

Alle Endpoints außer `register` verlangen `Authorization: Token <key>`.

```
POST /api/register/           {vorname, nachname, nickname, muttersprache}
                              → 201 {token, nickname}  (offen, Rate-Limit)
GET  /api/items/?level=A1     Übungswörter
GET  /api/items/{id}/
GET  /api/targets/?speaker=…  Referenzformanten (fürs Vokalviereck)
GET  /api/profile/            Übungsstatistik pro Laut + Profildaten
PUT  /api/profile/            {vorname, nachname, muttersprache} —
                              Nickname und Token bleiben unverändert
POST /api/recordings/         multipart: item_id, speaker (male|female|child), audio (WAV mono)
                              → analysiert synchron, antwortet mit result
GET  /api/recordings/         eigene Aufnahmen (Verlauf)
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

## Anleitung für Kirsten (Kuratorin)

Deine zwei Werkzeuge sind die **App** (Üben, Validieren) und der
**Django-Admin** (Wortlisten und Zielwerte pflegen):
https://mundwerk.proportiodivina.eu/admin/ — den Zugang (Benutzername +
Passwort) bekommst du von Thomas.

### 1. Mit der App validieren

1. APK von Thomas installieren (`mundwerk-kirsten.apk`); beim ersten
   Öffnen unter Menü (☰) → **Profil** prüfen: „Angemeldet als: kirsten“.
2. Beim Üben **„hohe Stimme“** wählen (die Zielwerte sind nach
   Stimmlage getrennt).
3. Jedes Wort **3× gut** und danach **bewusst falsch** sprechen
   (typische Lernerfehler nachahmen). Notiere jede Stelle, wo das
   App-Urteil von deinem Ohr abweicht: Wort, was du gesprochen hast,
   was die App sagte. Deine Aufnahmen bleiben gespeichert (Korpus-
   Einwilligung) und dienen später als Referenzmaterial.

### 2. Zielwerte (Referenzformanten) justieren

Im Admin unter **Api → Target segments**:

1. Laut und Stimmlage auswählen — z. B. `/yː/ (female)`.
2. Vier Zahlen bestimmen die Bewertung, alle in Hertz:
   - `f1_mean` / `f2_mean`: der **Zielwert** (Mitte der Zielzone —
     das Kreuz im Vokalviereck),
   - `f1_sd` / `f2_sd`: die **Toleranz** (Streuung; die Ellipse im
     Vokalviereck). Größere sd = die App wird nachsichtiger für
     diesen Laut in dieser Richtung.
3. Die Ampel rechnet aus beiden Abweichungen zusammen: **grün** unter
   2 Toleranzeinheiten, **gelb** unter 3,5, sonst **rot**.
4. Speichern — die Änderung wirkt **sofort** für alle Nutzer
   (Bewertung, Hinweise, Vokalviereck), ganz ohne Neustart. Praktischer
   Ablauf: Wert ändern → in der App dasselbe Wort neu sprechen →
   prüfen, ob das Urteil jetzt stimmt.

### 3. Wortlisten pflegen

Zwei Wege: einzeln im Django-Admin (**Api → Items**: Wort, IPA,
Niveau, Fokus-Laute), oder gesammelt per CSV:

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

Das Kommando läuft auf dem Server — Kirsten schickt ihre CSV einfach
an Thomas, der sie einspielt (oder pflegt kleinere Änderungen selbst
im Admin).

## Stand / bewusste Vereinfachungen

- **Segmentierung:** Forced Alignment per MFA (`MFA_BIN` in `.env`;
  conda-Env `mfa`, Modelle `german_mfa`). Liefert das Alignment den
  Fokus-Laut nicht (oder ist MFA aus), greift die Auto-Segmentierung
  (längster stimmhafter Abschnitt); `result.segments[].segmentierung`
  sagt, welcher Weg es war. Aufnahme+Analyse dauern damit ~8 s —
  wenn das stört: Celery-Task (POST → 202 + Polling).
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
