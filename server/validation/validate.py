#!/usr/bin/env python3
"""Mundwerk Phase 0 — Offline-Validierung der Analyse-Pipeline.

Nimmt eine WAV-Datei, misst F1/F2 des Zielvokals und vergleicht mit den
Referenzwerten. Die eigentliche Pipeline liegt in analysis/pipeline.py und
wird auch vom Django-Backend benutzt. Drei Betriebsarten:

1. --auto (Default bei Einzelvokal-Aufnahmen): findet automatisch den
   längsten stimmhaften, lauten Abschnitt und misst dort.
2. --textgrid rec.TextGrid: liest ein Alignment (z. B. vom Montreal Forced
   Aligner) und misst alle Vokale, für die Referenzwerte existieren.
3. --start/--end: manuell annotierte Segmentgrenzen in Sekunden.

Beispiele:
    python validate.py aufnahme_ie.wav --phone iː --speaker male
    python validate.py schoen.wav --textgrid schoen.TextGrid --speaker female
    python validate.py wort.wav --phone øː --start 0.31 --end 0.52
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import parselmouth
from parselmouth.praat import call

from analysis.pipeline import AnalysisError, analyze_recording
from analysis.reference_formants import TARGETS


def segments_from_textgrid(path: str, phones: set[str]) -> list[tuple[str, float, float]]:
    """Vokal-Intervalle aus einem TextGrid (z. B. MFA-Output, Tier 'phones')."""
    tg = parselmouth.read(path)
    n_tiers = call(tg, "Get number of tiers")
    tier = None
    for i in range(1, n_tiers + 1):
        if call(tg, "Get tier name", i).lower() in ("phones", "phone", "segments"):
            tier = i
            break
    if tier is None:
        tier = n_tiers  # MFA: letzter Tier ist üblicherweise 'phones'
    out = []
    for i in range(1, call(tg, "Get number of intervals", tier) + 1):
        label = call(tg, "Get label of interval", tier, i).strip()
        if label in phones:
            out.append((label,
                        call(tg, "Get start time of interval", tier, i),
                        call(tg, "Get end time of interval", tier, i)))
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("wav", help="Aufnahme (WAV, mono)")
    ap.add_argument("--phone", help="Zielvokal in IPA, z. B. iː øː aː")
    ap.add_argument("--speaker", choices=("male", "female", "child"), default="male")
    ap.add_argument("--textgrid", help="TextGrid mit Alignment (MFA)")
    ap.add_argument("--start", type=float, help="Segmentbeginn in s (manuell)")
    ap.add_argument("--end", type=float, help="Segmentende in s (manuell)")
    ap.add_argument("--json", action="store_true", help="Ausgabe als JSON")
    args = ap.parse_args()

    if args.textgrid:
        segments = segments_from_textgrid(args.textgrid, set(TARGETS))
        if not segments:
            sys.exit("Kein bekannter Vokal im TextGrid gefunden.")
    elif args.start is not None and args.end is not None:
        if not args.phone:
            sys.exit("--start/--end braucht --phone.")
        segments = [(args.phone, args.start, args.end)]
    else:
        if not args.phone:
            sys.exit("Ohne --textgrid bitte --phone angeben (Auto-Modus).")
        segments = [(args.phone, None, None)]

    results = []
    for phone, start, end in segments:
        try:
            results.append(analyze_recording(
                args.wav, phone, args.speaker,
                segment=(start, end) if start is not None else None))
        except AnalysisError as e:
            sys.exit(str(e))

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return
    for r in results:
        print(f"\n/{r['phone']}/  ({r['start']}–{r['end']} s)")
        print(f"  gemessen: F1 {r['f1']} Hz, F2 {r['f2']} Hz")
        if r["rating"] is None:
            print(f"  {r['note']}")
            continue
        print(f"  Ziel:     F1 {r['target_f1']} Hz, F2 {r['target_f2']} Hz"
              f"  (z: {r['z_f1']}, {r['z_f2']})")
        print(f"  Rating:   {r['rating'].upper()}  (Distanz {r['distanz']})")
        for fb in r["feedback"]:
            print(f"  → {fb}")


if __name__ == "__main__":
    main()
