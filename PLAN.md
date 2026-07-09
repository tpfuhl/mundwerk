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
   4. **Mustergültige Aufnahmen mit ⭐ markieren** (Button unter dem
      Ergebnis, nur für Korpus-Mitglieder sichtbar) und **Abweichungen
      notieren** (Wort, was gesprochen, was die App geurteilt hat) —
      überall dort, wo das App-Urteil vom geschulten Ohr abweicht.
   5. Kalibrieren: `manage.py calibrate_targets --speaker female`
      berechnet aus den ⭐-Aufnahmen Mittelwert/Streuung pro Laut und
      schreibt sie in die TargetSegments (erst `--dry-run`; mindestens
      5 Aufnahmen pro Laut). Feinschliff weiterhin von Hand im Admin —
      beides wirkt sofort, ohne Deployment.
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

4. **Segmentdiagnose statt Wort-Urteil** — siehe eigener Abschnitt unten;
   Antwort auf Kirstens Grundsatzkritik (Juli 2026).
5. **Kurskorrektur „Lautebene zuerst“** — siehe eigener Abschnitt unten
   (Kirsten, Juli 2026): Feedback-Sprache, F3/Dauer/Intensität,
   Vokal-Curriculum mit Referenz-Audio, sprecherunabhängige Bewertung.

- **Phase 2:** Kurzvokale, Umlaut-Minimalpaare, Vokalviereck-Visualisierung
  (Ist vs. Soll als Punkt im F1/F2-Raum).
- **Phase 3:** Konsonanten — Formanten reichen nicht: Frikative brauchen
  spektrale Momente (CoG für /ç/ vs. /ʃ/), Plosive VOT. Parselmouth kann
  das, aber es sind andere Messgrößen.
- **Phase 4:** Sätze/Prosodie: Pitch-Kontur (`snd.to_pitch()`), Vergleich
  mit Referenzkontur per DTW (Akzent, Satzmelodie).
- **Phase 5:** L1-spezifische Übungspfade, Userlexikon via G2P (MFA).

## Segmentdiagnose statt Wort-Urteil (Plan, Juli 2026)

Anstoß: Kirstens Befund am Wort „früh“ — **„flüh“ wird rot** (das
stimmhafte /l/ gerät in bzw. verschiebt die Messung), **„fküh“ wird
grün** (das /yː/ stimmt ja, und der Konsonant davor wird gar nicht
geprüft). Grundsatzkritik: Das Wort ist als kleinste Einheit zu groß;
bewertet und erklärt werden muss auf der Lautebene — beginnend bei
isolierten Lauten, wie beim Schreiben jeder Fehler einzeln geortet wird.

**Einordnung Praat/Parselmouth:** Parselmouth ist ein *Mess*-, kein
*Erkennungs*werkzeug. Es beantwortet „**Wie** wurde ein Laut
gesprochen?“ (Formanten, spektrale Momente, VOT, F0) — nicht
„**Welcher** Laut wurde gesprochen?“. Für Letzteres braucht es
Erkennung. Die Arbeitsteilung ist der eigentliche USP:
**Erkennung ortet den Fehler, Parselmouth-Messung erklärt ihn
artikulatorisch.** Beides zusammen leistet, was keine gängige App tut.

Warum das heutige System die beiden Fälle so behandelt:
- Geprüft werden nur die `focus_segments` des Items (Vokale). Ein
  falscher Konsonant („fküh“) ist schlicht außerhalb des Messfensters →
  fälschlich grün.
- MFA aligniert *erzwungen*: Wer „flüh“ sagt, bekommt trotzdem f‑ʁ‑yː
  ins TextGrid gestempelt; im Auto-Fallback (längster stimmhafter
  Abschnitt) wandert das stimmhafte /l/ sogar direkt in die
  Vokalmessung → fälschlich rot, und der wahre Fehler bleibt unbenannt.

*Stand: Schritt 1 + 2 sind serverseitig umgesetzt (Item-Felder `kind`,
`mfa_pron`, `error_variants`; Varianten-Lexikon in `analysis/alignment.py`;
`result.lautfolge` mit benannten Abweichungen; Seeds: 7 Laut-Items +
„früh“ mit Fehlervarianten). Es fehlen: App-UI (Laut-Übungen anbieten,
`lautfolge`/Hinweis anzeigen) und Schritt 3 + 4. — Nach Kirstens
Kurskorrektur (nächster Abschnitt) ruht die Wortebene vorerst; das
Alignment bleibt als Infrastruktur bestehen.*

### Schritt 1 — Isolierte Laute als eigener Übungstyp (didaktisch, sofort)
Neuer Item-Typ „Laut“ (isolierte Vokale, später haltbare Konsonanten
/s ʃ ç x f v l m n ŋ/): Der Lernende klärt zuerst, welche Laute er kann
und welche nicht — Kirstens Einstiegspunkt. Technisch der dankbarste
Fall: kein Alignment nötig, die Auto-Segmentierung (längster
stimmhafter/lauter Abschnitt) ist genau dafür gebaut. Progression dann
Laut → Silbe/Minimalpaar → Wort → Phrase (Phonosyntaktik) →
Satz/Prosodie (= bisherige Phase 4).

### Schritt 2 — Fehlerhypothesen-Alignment: Substitutionen orten
Klassisches Verfahren der Mispronunciation Detection („Extended
Recognition Network“), passt exakt auf den vorhandenen Stack: Pro Item
werden neben der Soll-Lautung die **typischen Fehlaussprachen als
Aussprachevarianten** in ein eigenes MFA-Lexikon geschrieben —
für „früh“ etwa `fʁyː | flyː | fkyː | fyː`. MFA wählt beim Alignment
die akustisch beste Variante; wählt es eine Fehlervariante, ist der
Fehler geortet **und benannt**: „Sie haben /l/ statt /ʁ/ gesprochen.“
- Die Fehlerhypothesen (gern L1-spezifisch, → Phase 5) sind Kirstens
  Domäne: neues Feld `error_variants` am Item, Pflege im Admin/CSV.
- Kein neues Framework — nur ein generiertes Lexikon beim `align_one`.
- Nebeneffekt: Die Vokalmessung wird robuster, weil die Segmentgrenzen
  zur tatsächlich gesprochenen Lautfolge passen.

### Schritt 3 — Alle Segmente bewerten, nicht nur den Fokusvokal
Feedback pro Phon (Ampelleiste entlang des Wortes statt eines
Gesamturteils). Vokale: Formanten wie bisher. Konsonanten sind mit
Parselmouth messbar, aber mit anderen Messgrößen (präzisiert Phase 3):

| Lautklasse | Messgröße (Parselmouth) | unterscheidet z. B. |
|---|---|---|
| Frikative | spektraler Schwerpunkt (CoG) + Streuung | /ç/ ↔ /ʃ/ ↔ /s/ |
| Plosive | VOT (Burst→Stimmeinsatz), Stimmhaftigkeit | /d/ ↔ /t/, Aspiration |
| Liquide | F3 + Formantverlauf, Stimmhaftigkeit | /l/ ↔ /ʁ/ |
| Nasale | Nasal-Formant, Antiformant | /m/ ↔ /n/ ↔ /ŋ/ |

### Schritt 4 (später) — Offener Phonemerkenner als Backstop
Für Fehler, die niemand antizipiert hat: ein CTC-Phonemerkenner
(z. B. wav2vec2 „espeak“-Phonemmodelle, CPU-tauglich) transkribiert,
was *tatsächlich* gesagt wurde; Levenshtein-Abgleich mit der Ziel-IPA
liefert Einfügungen/Auslassungen/Substitutionen. Erst angehen, wenn
Schritt 2 an Grenzen stößt — die Variantenlösung deckt die häufigen,
didaktisch erklärbaren Fälle bereits ab und bleibt deutbar.

## Kurskorrektur: Lautebene zuerst (Kirsten, Juli 2026)

**Leitprinzip (Kirsten, verbindlich): Mundwerk ist ein Lehr- und
Lerntool und muss bei den kleinsten Einheiten beginnen — den isolierten
Lauten — und sich von dort didaktisch hocharbeiten:**

> Phone → offene Silben → geschlossene Silben → Wörter → Syntagmen → Sätze

Die App wird auf diese Progression umgestellt; die isolierten Laute sind
der Einstieg und für die nächste Zeit der alleinige Fokus. Die
Wortkorrektur bleibt technisch erhalten, ist aber didaktisch verfrüht.

**Warum Wort-Nachsprechen mit reiner Vokalmessung irreführt** (Kirstens
Beleg): „Tee“ als „Che“ gesprochen (ch wie in „ach“) bekam grünes Licht.
Beide Konsonanten sind stimmlos, das Wort einsilbig — die Formantmessung
des /eː/ gelingt problemlos, also grün, obwohl der Anlaut komplett falsch
ist. Setzt man einen stimmhaften Laut (z. B. Nasal) davor, verzerrt
dessen Frequenz umgekehrt die Vokalmessung. **Fazit: Ohne verlässliche
Segmentierung *und* Bewertung aller Laute ist ein Wort-Urteil nicht
tragfähig.** Beim isolierten Laut stellt sich das Problem nicht — es
gibt nur einen Laut, die Auto-Segmentierung genügt.

Konkrete Einwände und was daraus folgt, in Umsetzungsreihenfolge:

### 1. Wortebene ruht
Solange pro Wort nur ein Fokusvokal bewertet wird, suggeriert das
Wort-Urteil mehr, als gemessen wurde („komplett richtig?“ kann die App
nicht beantworten; siehe „Tee“/„Che“). Wort-Items und
Fehlerhypothesen-Alignment bleiben als Infrastruktur, aber Kuratierung,
Feinschliff und App-UI konzentrieren sich auf die isolierten Vokale.
(Mehrere focus_segments
pro Item kann das Backend übrigens schon — die Seeds nutzen es nur
nicht.)

### 2. Feedback-Sprache nach Artikulatoren trennen (klein, sofort)
Didaktische Konvention für alle Hinweistexte:
- **F1 ↔ Mundöffnung** (Kiefer) — nicht „Zungenhöhe“,
- **F2 ↔ Zunge** horizontal (vorn/hinten),
- **F3/Rundung ↔ Lippen**.
Schema „Mund …, Zunge …, Lippen …“ statt der bisherigen Mischung.
Dazu: Feedbacktexte aus `reference_formants.py` in die DB verlagern,
damit Kirsten sie im Admin formuliert (analog zu den Zielwerten).

### 3. Mehr Messgrößen: F3, Dauer, Intensität (klein, sofort)
Messzentrum ist gesichert (Median über das mittlere Drittel — bereits
implementiert), aber pro Segment zusätzlich messen und speichern:
- **F3** (Lippenrundung; fließt in die /yː øː uː oː/-Bewertung ein),
- **Dauer** (Lang/Kurz-Opposition, Phase 2),
- **Intensität** (Wortakzent später: úmfahren/umfáhren — primär
  Lautstärke, sekundär Länge; Formanten unterscheiden die beiden nicht).
Alles Parselmouth-Standard (`to_intensity`, Segmentgrenzen, Formant 3).
Erst speichern, später bewerten.

### 4. Vokal-Curriculum nach dem Vokaltrapez (App-UI)
Drei Gruppen als Lernpfad, innerhalb der Gruppe variiert primär der
Öffnungsgrad (Kiefer):
1. vordere ungerundete Vokale /iː eː/,
2. vordere gerundete /yː øː/ (Zunge wie Gruppe 1, nur Lippen runden),
3. hintere gerundete /uː oː/ (+ /aː/ als offener Sonderfall).
Pro Laut **vor** der Übung: Artikulationserklärung mit
Sagittalschnitt-Grafik (erst statisch, später animiert) und
**Referenz-Audio** zum Nachsprechen.

*Server umgesetzt:* `Item.gruppe` (Trapez-Gruppe), `Item.beschreibung`
(Artikulationserklärung, Seed für die 7 Laute), `Item.reference_audio`
(Upload im Admin). API: `?gruppe=`-Filter, `has_audio` im Serializer,
authentifizierter Stream `GET /api/items/{id}/audio/` (Apache serviert
`/media/` bewusst nicht). CSV-Import kennt `gruppe`/`beschreibung`.

*App umgesetzt (Punkt 5):* Die App startet jetzt auf der **Laut-Auswahl**
(drei Vokaltrapez-Gruppen als Lernpfad). Pro Laut ein Übungs-Screen mit
Artikulationserklärung und — sobald Referenz-Audio hochgeladen ist —
einem „Vorsprechen anhören“-Knopf (`ReferencePlayer`, MediaPlayer).
Wortübungen sind hinter den „Wörter“-Umschalter gerückt und tragen den
ehrlichen Hinweis, dass nur der markierte Vokal bewertet wird. Auf echtem
Gerät gegen die Produktion verifiziert.
*Offen:* Sagittalschnitt-Grafiken (Platzhalter bis Kirstens Grafiken
vorliegen); Referenz-Audios muss Kirsten im Admin einsprechen/hochladen.

### 5. Sprecherunabhängige Bewertung statt male/female-Hz-Tabellen
Kirstens Punkt: ein /aː/ bleibt ein /aː/, egal wer spricht — es zählen
die Relationen, nicht absolute Frequenzen. Operationalisierung:
- **Bark-Raum — umgesetzt** (`pipeline.hz_to_bark`, Traunmüller 1990):
  Der Vergleich läuft jetzt auf der gehörgerechten Bark-Skala,
  `result.segments[].raum = "bark"`. **Ehrliche Bilanz:** Solange die
  Zielwerte *pro Stimmlage* in Hz gepflegt sind und jede Dimension durch
  ihre eigene (mit-linearisierte) Streuung geteilt wird, hebt sich der
  perzeptive Effekt nahe am Ziel fast auf — die Ampel ändert sich kaum.
  Bark ist damit die *richtige Skala* und die Vorbereitung, aber noch
  nicht die Sprecherunabhängigkeit. Der Aufwand war klein, das Risiko
  null (Schwellen bleiben gültig).
- **Lobanov-Normalisierung — der eigentliche Hebel, noch offen:** nach
  kurzer Onboarding-Kalibrierung (User spricht /aː iː uː/) z-normieren;
  ersetzt die Stimmlagen-Auswahl komplett, Standard der Soziophonetik.
  Braucht App-Onboarding + eine Kalibrier-Speicherung pro User — daher
  eigener Block (nach dem Vokal-Curriculum sinnvoll).
- Nüchtern anzumerken: der rohe Abstand F2−F1 in Hz ist selbst *nicht*
  sprecherunabhängig; Bark/Lobanov/Nearey sind genau die sauberen
  Formalisierungen der „relativen Abstände“. Und bei hoher
  Grundfrequenz (Kinder) bleibt Formantmessung prinzipiell unschärfer
  (weit auseinanderliegende Harmonische) — daran ändert auch
  Normalisierung nichts.

## Offene Punkte

- Referenz-Formantwerte für deutsche Vokale: Startpunkt sind publizierte
  Mittelwerte (z. B. Pätzold & Simpson 1997, Kiel Corpus); langfristig eigene
  Referenzdaten von Kirsten/Thomas einpflegen.
- Audio-Format Android → Server: unkomprimiertes WAV 16 kHz/16 bit mono
  (Formantanalyse verträgt Lossy-Artefakte schlecht — kein AMR/Opus).
- Datenschutz: Aufnahmen sind personenbezogene Daten → Löschkonzept, DSGVO.
