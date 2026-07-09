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
GET  /api/items/?level=A1&kind=laut   Übungen (kind: laut|wort|satz)
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

Antwort (`result.segments[]`): pro Fokus-Phone `f1/f2` (gemessen und
bewertet), `f3`, `dauer_ms`, `intensitaet_db` (gemessen, noch nicht
bewertet — Lippenrundung/Quantität/Wortakzent), `target_f1/f2`,
`z_f1/z_f2`, `distanz`, `rating` (grün/gelb/rot), `feedback`
(artikulatorische Hinweise), `start/end` (Segment in s). Gemessen wird
im mittleren Drittel des Segments (Koartikulation an den Rändern).

Bei Wort-Items mit Soll-Lautung (`mfa_pron`) zusätzlich
`result.lautfolge`: `soll`/`ist` (Phonfolgen), `abweichungen`
(`[{typ: ersetzt|fehlt|zuviel, position, soll, ist, text}]`, z. B.
„/l/ statt /ʁ/ gesprochen“) und ggf. `hinweis` (kuratierter Text zur
erkannten Fehlervariante).

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
   was die App sagte.
4. War eine Aufnahme mustergültig, tippe unter dem Ergebnis auf
   **„☆ Als Referenzaufnahme markieren“** (den Button siehst nur du
   bzw. Thomas). Aus diesen ⭐-Aufnahmen berechnen wir später die
   Zielwerte — deine korrekte Aussprache wird damit wörtlich zur
   Referenz. Falls du einen Stern versehentlich setzt: nochmal tippen
   entfernt ihn; auch im Admin (Recordings, Spalte „Ist referenz“)
   lässt er sich setzen und entfernen.

### 2. Zielwerte (Referenzformanten) justieren

**Automatisch aus euren ⭐-Aufnahmen** (macht Thomas auf dem Server,
sobald ≥ 5 markierte Aufnahmen pro Laut vorliegen):

```bash
manage.py calibrate_targets --speaker female --dry-run   # Vorschau alt → neu
manage.py calibrate_targets --speaker female             # schreiben
```

Das berechnet pro Laut Mittelwert und Streuung aus allen markierten
Aufnahmen (Untergrenzen: F1 ±30 Hz, F2 ±60 Hz, damit die Bewertung
nicht zu streng wird) und aktualisiert die TargetSegments.

**Von Hand (Feinschliff)** im Admin unter **Api → Target segments**:

1. Laut und Stimmlage auswählen — z. B. `/yː/ (female)`.
2. Vier Zahlen bestimmen die Bewertung, alle in Hertz:
   - `f1_mean` / `f2_mean`: der **Zielwert** (Mitte der Zielzone —
     das Kreuz im Vokalviereck),
   - `f1_sd` / `f2_sd`: die **Toleranz** (Streuung; die Ellipse im
     Vokalviereck). Größere sd = die App wird nachsichtiger für
     diesen Laut in dieser Richtung.
3. Die Ampel rechnet aus beiden Abweichungen zusammen: **grün** unter
   2 Toleranzeinheiten, **gelb** unter 3,5, sonst **rot**. Der Vergleich
   läuft auf der gehörgerechten **Bark-Skala** (Zielwerte bleiben in Hz;
   nahe am Ziel bleibt die Bewertung praktisch wie zuvor).
4. Speichern — die Änderung wirkt **sofort** für alle Nutzer
   (Bewertung, Hinweise, Vokalviereck), ganz ohne Neustart. Praktischer
   Ablauf: Wert ändern → in der App dasselbe Wort neu sprechen →
   prüfen, ob das Urteil jetzt stimmt.

**Korrekturtexte** im Admin unter **Api → Feedback rules**: pro Laut,
Formant (F1/F2) und Richtung (zu hoch / zu niedrig) ein Hinweissatz.
Didaktische Konvention — die Artikulatoren nicht vermischen:

- **F1 ↔ Mundöffnung** (Kiefer): „Mund weiter öffnen / fast schließen“.
- **F2 ↔ Zunge horizontal**: „Zunge nach vorn schieben / zurückziehen“.
- **Rundung/F3 ↔ Lippen**: „Lippen runden“.

Also z. B. „Mund fast schließen, Zunge vorn“ statt „Zunge nach oben“.
Fehlt eine Regel, greift der eingebaute Text; Änderungen wirken sofort.

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

Optionale Spalten (Segmentdiagnose, siehe PLAN.md):

- `kind` — `laut` (isoliert gehaltener Laut, Einstiegsübungen),
  `wort` (Default) oder `satz`.
- `pron` — Soll-Lautung in MFA-Phonen, leerzeichengetrennt: `f ʁ yː`.
- `varianten` — typische Fehlaussprachen, durch `|` getrennt:
  `f l yː | f k yː | f yː`. Die App aligniert dann gegen alle Varianten
  und meldet z. B. „/l/ statt /ʁ/ gesprochen“. **Der didaktische
  Hinweistext pro Variante wird im Admin gepflegt** (Api → Items →
  Feld „Error variants“: `[{"pron": "f l yː", "hinweis": "…"}]`) und
  überlebt einen erneuten CSV-Import.

Fehlt eine optionale Spalte in der CSV, bleiben die im Admin gepflegten
Werte unangetastet. Achtung: `pron`/`varianten` müssen Phone aus dem
`german_mfa`-Phonset verwenden, sonst scheitert das Alignment und die
App fällt auf die Auto-Segmentierung zurück (Warnung im Server-Log).

Das Kommando läuft auf dem Server — Kirsten schickt ihre CSV einfach
an Thomas, der sie einspielt (oder pflegt kleinere Änderungen selbst
im Admin).

## Stand / bewusste Vereinfachungen

- **Segmentierung:** Forced Alignment per MFA (`MFA_BIN` in `.env`;
  conda-Env `mfa`, Modelle `german_mfa`). Liefert das Alignment den
  Fokus-Laut nicht (oder ist MFA aus), greift die Auto-Segmentierung
  (längster stimmhafter Abschnitt); `result.segments[].segmentierung`
  sagt, welcher Weg es war. Items mit `kind=laut` (isolierte Laute)
  überspringen MFA bewusst. Aufnahme+Analyse dauern damit ~8 s —
  wenn das stört: Celery-Task (POST → 202 + Polling).
- **Fehlerhypothesen-Alignment:** Hat ein Item `mfa_pron` +
  `error_variants`, wählt MFA die akustisch beste Aussprachevariante;
  `result.lautfolge` enthält dann Soll/Ist-Lautfolge, benannte
  Abweichungen („/l/ statt /ʁ/ gesprochen“) und Kirstens Hinweis zur
  erkannten Variante. Arbeitsbeispiel: Seed-Item „früh“.
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
