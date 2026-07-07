#!/usr/bin/env python3
"""Synthetische Testvokale erzeugen (Klatt-Synthese via Praat).

Erzeugt WAV-Dateien mit bekannten Formantwerten, um validate.py zu testen,
ohne dass schon echte Aufnahmen vorliegen. Zusätzlich zu den "idealen"
Vokalen werden typische Fehlproduktionen erzeugt (z. B. yː als uː
gesprochen), an denen die Diskriminierung geprüft werden kann.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from parselmouth.praat import call

from analysis.reference_formants import TARGETS

OUT = os.path.join(os.path.dirname(__file__), "test_audio")

# (Dateiname, deklarierter Zielvokal, tatsächlich synthetisierte F1/F2)
CASES = []
for phone, by_speaker in TARGETS.items():
    f1, _, f2, _ = by_speaker["male"]
    CASES.append((f"{phone}_gut", phone, f1, f2))
# Typische Fehler: Umlaut ohne Zungenposition → Hinterzungenvokal
CASES += [
    ("yː_als_uː", "yː", 300, 800),    # yː gesprochen wie uː
    ("øː_als_oː", "øː", 370, 780),    # øː gesprochen wie oː
    ("iː_zu_offen", "iː", 420, 2100), # iː mit zu offenem Mund
]


def synthesize(f1: float, f2: float, path: str, duration=0.6, pitch=120) -> None:
    f3 = max(2500.0, f2 + 400)
    kg = call("Create KlattGrid from vowel", "vowel", duration, pitch,
              f1, 60, f2, 90, f3, 150, 3500, 0.05, 1000)
    snd = call(kg, "To Sound")
    call(snd, "Scale intensity", 70)
    snd.save(path, "WAV")


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    for name, phone, f1, f2 in CASES:
        path = os.path.join(OUT, f"{name}.wav")
        synthesize(f1, f2, path)
        print(f"{path}  (Ziel /{phone}/, synthetisiert F1={f1}, F2={f2})")


if __name__ == "__main__":
    main()
