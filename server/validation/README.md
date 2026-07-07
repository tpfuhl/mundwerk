# Mundwerk — Phase 0: Offline-Validierung der Analyse-Pipeline

Bevor App und Backend gebaut werden, muss diese Pipeline beweisen, dass sie
gute von falscher Aussprache unterscheiden kann: WAV → Segmentierung →
Formantmessung (Parselmouth/Praat) → Vergleich mit Referenz → Feedback.

## Setup

```bash
cd server
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Dateien

- `validate.py` — das Validierungsskript (siehe `--help`)
- `../analysis/` — die eigentliche Pipeline (`pipeline.py`) und die
  Referenz-Formantwerte + Feedback-Regeln (`reference_formants.py`),
  gemeinsam genutzt von diesem Skript und dem Django-Backend
- `make_test_vowels.py` — erzeugt synthetische Testvokale (Klatt-Synthese)
  in `test_audio/`, inkl. typischer Fehlproduktionen

## Schnelltest mit synthetischen Vokalen

```bash
cd server/validation
../.venv/bin/python make_test_vowels.py
../.venv/bin/python validate.py test_audio/yː_gut.wav    --phone yː   # → GRÜN
../.venv/bin/python validate.py test_audio/yː_als_uː.wav --phone yː   # → ROT
```

Erwartung: alle `*_gut.wav` grün, die Fehlproduktionen rot/gelb mit dem
passenden artikulatorischen Hinweis.

## Test mit echten Aufnahmen (der eigentliche Validierungsschritt)

1. **Aufnehmen:** lange Vokale isoliert und gehalten (~1 s), z. B. mit
   Audacity oder `arecord -f S16_LE -r 16000 -c 1 ie.wav`.
   Pro Vokal /iː yː uː eː øː oː aː/:
   - eine gute Produktion
   - eine absichtlich falsche (z. B. yː als uː, iː mit offenem Mund)
   Idealerweise von beiden Teammitgliedern (♂/♀ — Normalisierung testen!).
2. **Auswerten:**
   ```bash
   ../.venv/bin/python validate.py ie_gut.wav --phone iː --speaker male
   ../.venv/bin/python validate.py ie_gut_kirsten.wav --phone iː --speaker female
   ```
   Im Auto-Modus findet das Skript den Vokal selbst (längster stimmhafter,
   lauter Abschnitt). Alternativ `--start/--end` in Sekunden.
3. **Erfolgskriterium:** gute Produktionen grün/gelb, falsche rot, und der
   Feedbacktext benennt den tatsächlich gemachten Fehler. Wo das nicht
   klappt: Referenzwerte/SDs in `reference_formants.py` justieren — genau
   dafür ist diese Phase da.

## Nächster Schritt: ganze Wörter (Forced Alignment)

Für Wörter wie „schön“ braucht es die Segmentierung per Montreal Forced
Aligner (MFA). Installation (conda erforderlich):

```bash
conda create -n mfa -c conda-forge montreal-forced-aligner
conda activate mfa
mfa model download acoustic german_mfa
mfa model download dictionary german_mfa
mfa align korpus_ordner/ german_mfa german_mfa ausgabe_ordner/
```

(Der Korpus-Ordner enthält je Aufnahme `wort.wav` + `wort.txt` mit der
Orthographie.) Das erzeugte TextGrid dann direkt auswerten:

```bash
../.venv/bin/python validate.py schoen.wav --textgrid schoen.TextGrid --speaker male
```

**Achtung:** Das MFA-Modell `german_mfa` etikettiert Phone in IPA, aber
teils mit anderen Symbolen als unsere Referenztabelle (z. B. Längenzeichen).
Beim ersten echten TextGrid die Labels prüfen und ggf. ein Mapping in
`validate.py` ergänzen.

## Bekannte Grenzen (bewusst aufgeschoben)

- Sprechernormalisierung ist nur grob (male/female-Tabellen + max_formant);
  Lobanov-Normalisierung mit Kalibrierungsvokalen kommt in Phase 1.
- Synthetische Vokale validieren nur die Messkette, nicht die Streuung
  echter Sprache — daher Schritt „echte Aufnahmen“ nicht überspringen.
- `--json` liefert die Ausgabe im Format, das später die API zurückgibt.
