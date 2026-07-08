# Mundwerk — Projektplan

Aussprache-App für Deutsch-Lernende: interaktive Korrektur der Eigenproduktion
per Formantanalyse. Team: Kirsten Jänich (Phonetik/DaF), Thomas Pfuhl (Computerlinguistik).

## Architektur

```
Android (Kotlin)                    Server (Django/DRF)
┌──────────────────┐               ┌─────────────────────────────┐
│ Wort-/Satzliste  │               │ DRF-API                     │
│ AudioRecord      │──WAV/16kHz──▶ │ 1. Forced Alignment (MFA)   │
│ Upload (Retrofit)│               │ 2. Formantanalyse           │
│ Feedback-Screen  │◀──JSON─────── │    (Parselmouth)            │
└──────────────────┘               │ 3. Vergleich + Feedback     │
                                   └─────────────────────────────┘
```

**Kernentscheidung:** Praat wird nicht als externes Programm angesprochen,
sondern über **Parselmouth** (Python-Binding, bettet den Praat-Kern ein) —
die gesamte Pipeline läuft in einem Python-Prozess und liest auch die
TextGrids des Aligners.

## Die drei fachlichen Kernprobleme

### 1. Segmentierung (Forced Alignment)
Bevor Formanten verglichen werden können, muss bekannt sein, wo im Signal
z. B. das /øː/ von „schön“ liegt.

- **Montreal Forced Aligner (MFA)** — Empfehlung. Läuft lokal auf dem Server,
  deutsches Akustikmodell + Lexikon vorhanden, IPA-kompatibel, bringt G2P mit
  (wichtig für das Userlexikon in Phase 5).
- Alternative: WebMAUS (BAS München) — exzellent für Deutsch, aber externe
  Abhängigkeit und für kommerzielle Nutzung lizenzpflichtig.

### 2. Sprechernormalisierung
F1/F2 sind zwischen Kind, Frau, Mann absolut nicht vergleichbar
(Vokaltraktlänge). Lösung: kurze **Kalibrierungsphase beim Onboarding**
(User spricht /aː iː uː/), daraus Lobanov-Normalisierung oder
Skalierungsfaktor. Ohne Normalisierung: Fehlalarme am Fließband.
Außerdem: `maximum_formant` in der Analyse sprecherabhängig setzen
(♂ ~5000 Hz, ♀ ~5500 Hz, Kinder höher).

### 3. Feedback-Mapping (der USP)
Regelbasierte Tabelle: Abweichungsrichtung → artikulatorischer Hinweis.

| Befund | Feedback |
|---|---|
| F1 zu hoch bei /iː/ | „Mund zu offen, Zunge höher“ |
| F2 zu niedrig bei /yː/ | typischer Fehler /uː/: „Zungenposition wie bei ‚ie‘, nur Lippen runden“ |
| F2 zu hoch bei /uː/ | „Lippen stärker runden, Zunge weiter hinten“ |

Das ist das eigentliche Expertenwissen (Kirstens Domäne).
Später: L1-spezifische Fehlerhypothesen priorisieren.

## Datenmodell (Django, Skizze)

```python
class Item(models.Model):          # Wort oder Satz
    text = models.CharField(max_length=200)
    ipa = models.CharField(max_length=200)
    level = models.CharField(max_length=10)   # A1..C2
    focus_segments = models.JSONField()        # ["øː", "ç"]

class TargetSegment(models.Model): # Expertenwissen
    phone = models.CharField(max_length=10)    # IPA
    f1_mean = models.FloatField(); f1_sd = models.FloatField()
    f2_mean = models.FloatField(); f2_sd = models.FloatField()
    feedback_rules = models.JSONField()

class Recording(models.Model):
    user = models.ForeignKey(User, ...)
    item = models.ForeignKey(Item, ...)
    audio = models.FileField()
    result = models.JSONField(null=True)       # Alignment + Formanten + Rating
```

## API

```
POST /api/recordings/        (multipart: item_id, audio.wav)
     → 202, task_id          (Analyse asynchron: Celery/Redis, MFA braucht 1–3 s)
GET  /api/recordings/{id}/   → { rating, segments: [{phone, f1, f2, target,
                                 deviation, feedback}] }
GET  /api/items/?level=A2
```

## Analyse-Pipeline (Kern)

```python
import parselmouth

snd = parselmouth.Sound("rec.wav")
formants = snd.to_formant_burg(max_number_of_formants=5,
                               maximum_formant=5500)  # sprecherabhängig!
# Pro Segment (aus MFA-TextGrid): Median von F1/F2 über das mittlere
# Drittel des Segments (stabiler gegen Transitionen als ein Einzelmesspunkt)
```

## Phasenplan

- **Phase 0 (jetzt): Offline-Validierung.** Skript, das WAV → Alignment →
  Formanten → Vergleich durchspielt. Mit eigenen Aufnahmen (gute vs.
  absichtlich falsche Aussprache) testen. **Wenn die Diskriminierung hier
  nicht funktioniert, funktioniert die App nicht.**
  → `server/validation/` in diesem Repo.
- **Phase 1 (MVP):** Nur lange Vokale in Einzelwörtern
  (/iː yː uː eː øː oː aː/) — dort ist Formantanalyse am zuverlässigsten.
  Feste Wortliste, Kalibrierung, Ampel-Rating + ein Hinweissatz.
  Android: Aufnahme (AudioRecord, 16 kHz mono WAV), Upload (Retrofit),
  Feedback-Screen. Django-Backend mit obigem Datenmodell.
- **Phase 1b — Nutzer & Daten** *(eingeschoben nach dem Deployment)*:
  - ✅ Privacy: jeder API-User sieht nur eigene Aufnahmen.
  - ✅ Audio-Lebenszyklus: Upload wird nach der Analyse gelöscht (Ergebnis
    bleibt); Ausnahme Gruppe „korpus“ (Einwilligung zur Aufbewahrung für
    die Referenzwert-Kalibrierung). Sicherheitsnetz: `manage.py
    prune_audio` per Cron. Das ist zugleich das DSGVO-Löschkonzept.
  - ✅ Profil/Verlauf: `GET /api/profile/` (Übungszähler, Ø-Distanz pro
    Vokal) + Verlaufs-Screen in der App; Audio bleibt lokal auf dem Gerät.
  - ✅ Registrierung statt einkompiliertem Token: Registrierungs-Screen
    beim ersten Start (Vorname, Nachname, Nickname, Muttersprache
    ISO 639-1) → `POST /api/register/` → Token wird app-privat
    gespeichert. Ein Token pro User ist der Normalfall und skaliert
    problemlos — nur die manuelle Vergabe tat es nicht.
  - ✅ Wortlisten-Pipeline: CSV-Import (`manage.py import_items`, erkennt
    Komma/Semikolon, aktualisiert statt dupliziert), Kuratierung im Admin
    durch Kirsten (Minimalpaare, Niveaus, L1-Bezug).
  - *Inzwischen außerdem ergänzt:* Hamburger-Menü (Profil-Editor,
    Hilfe, Über), App-Icon und Logo aus der Wortmarke, Git-basierte
    Versionsnummer, Build-Varianten dev/learner.

### Nächste Schritte (Stand Juli 2026, in dieser Reihenfolge)

1. **Referenzwert-Validierung mit echten Stimmen** *(kein Code — Thomas &
   Kirsten)*. Wichtigster fachlicher Schritt — alles Weitere baut darauf.
   Konkretes Protokoll:
   1. App installieren: Thomas baut die APK mit dem jeweiligen Token
      (`mundwerk-kirsten.apk` liegt bereit). Kontrolle: Menü → Profil
      zeigt den richtigen Nickname; dort auch das Profil ausfüllen.
   2. Stimmlage wählen: Thomas „tiefe Stimme“, Kirsten „hohe Stimme“ —
      danach richten sich die Zielwerte.
   3. Pro Übungswort: **3× gut aussprechen**, dann **bewusst falsch**
      (typische Fehler produzieren: /yː/ als /uː/, /øː/ als /oː/,
      /iː/ zu offen …). Ampel, Hinweistext und Vokalviereck beobachten.
   4. **Abweichungen notieren** (Wort, was gesprochen, was die App
      geurteilt hat) — überall dort, wo das App-Urteil vom geschulten
      Ohr abweicht: falscher Alarm bei guter Aussprache oder Grün bei
      absichtlich falscher.
   5. Auswertung zu zweit: Verlauf ansehen (Ø-Distanz pro Laut) und die
      **TargetSegments im Django-Admin justieren** — Schritt-für-Schritt-
      Anleitung dafür in `server/README.md` („Anleitung für Kirsten“).
      Änderungen wirken sofort in Bewertung und Vokalviereck, ohne
      Deployment.
   6. Die Aufnahmen von Thomas & Kirsten bleiben gespeichert
      (Korpus-Gruppe) und können später mit `validation/validate.py`
      nachvermessen werden.
2. ✅ **MFA-Integration**: Forced Alignment mit dem Montreal Forced
   Aligner (mfa align_one, conda-Env auf dem Server, german_mfa) →
   beliebige Wörter statt vokal-dominanter Einsilber. Fallback bleibt
   die Auto-Segmentierung (result: segmentierung mfa|auto). ~8 s pro
   Aufnahme synchron; Celery/Redis erst, wenn das zu langsam wird.
3. ✅ **Vokalviereck-Visualisierung** in der App: alle Referenzvokale,
   1-SD-Zielzone, eigene Produktion mit Linie zum Ziel; Achsen in
   Phonetik-Konvention. Referenzpunkte kommen aus /api/targets/ (DB) —
   Kirstens Admin-Justierungen wirken direkt.

- **Phase 2:** Kurzvokale, Umlaut-Minimalpaare, Vokalviereck-Visualisierung
  (Ist vs. Soll als Punkt im F1/F2-Raum).
- **Phase 3:** Konsonanten — Formanten reichen nicht: Frikative brauchen
  spektrale Momente (CoG für /ç/ vs. /ʃ/), Plosive VOT. Parselmouth kann
  das, aber es sind andere Messgrößen.
- **Phase 4:** Sätze/Prosodie: Pitch-Kontur (`snd.to_pitch()`), Vergleich
  mit Referenzkontur per DTW (Akzent, Satzmelodie).
- **Phase 5:** L1-spezifische Übungspfade, Userlexikon via G2P (MFA).

## Offene Punkte

- Referenz-Formantwerte für deutsche Vokale: Startpunkt sind publizierte
  Mittelwerte (z. B. Pätzold & Simpson 1997, Kiel Corpus); langfristig eigene
  Referenzdaten von Kirsten/Thomas einpflegen.
- Audio-Format Android → Server: unkomprimiertes WAV 16 kHz/16 bit mono
  (Formantanalyse verträgt Lossy-Artefakte schlecht — kein AMR/Opus).
- Datenschutz: Aufnahmen sind personenbezogene Daten → Löschkonzept, DSGVO.
