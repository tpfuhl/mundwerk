"""Referenzformanten aus als Referenz markierten Aufnahmen kalibrieren.

Sammelt alle Aufnahmen mit ist_referenz=True der angegebenen Stimmlage,
gruppiert die gemessenen F1/F2 pro Laut und schreibt Mittelwert und
Standardabweichung in die TargetSegments — Kirstens (bzw. Thomas')
korrekte Produktionen werden damit buchstäblich zur Referenz.

    manage.py calibrate_targets --speaker female [--phone yː]
                                [--min-count 5] [--dry-run]

Schutzmechanismen:
- Läufe mit weniger als --min-count Datenpunkten pro Laut werden
  übersprungen (Warnung) — eine Referenz aus 2 Aufnahmen wäre Zufall.
- Untergrenzen für die Streuung (F1: 30 Hz, F2: 60 Hz), damit sehr
  konsistente Sprecher die Bewertung nicht übertrieben streng machen.
"""

import statistics

from django.core.management.base import BaseCommand, CommandError

from api.models import Recording, TargetSegment

SD_FLOOR_F1 = 30.0
SD_FLOOR_F2 = 60.0


class Command(BaseCommand):
    help = "Berechnet TargetSegments aus referenz-markierten Aufnahmen."

    def add_arguments(self, parser):
        parser.add_argument("--speaker", required=True,
                            choices=("male", "female", "child"))
        parser.add_argument("--phone", help="nur diesen Laut kalibrieren")
        parser.add_argument("--min-count", type=int, default=5)
        parser.add_argument("--dry-run", action="store_true",
                            help="nur berichten, nichts speichern")

    def handle(self, *args, **options):
        speaker = options["speaker"]
        recordings = Recording.objects.filter(
            ist_referenz=True, speaker=speaker, status="done")
        samples = {}   # phone -> {"f1": [...], "f2": [...]}
        for recording in recordings:
            for seg in (recording.result or {}).get("segments", []):
                phone = seg.get("phone")
                if options["phone"] and phone != options["phone"]:
                    continue
                if seg.get("f1") is None or seg.get("f2") is None:
                    continue
                s = samples.setdefault(phone, {"f1": [], "f2": []})
                s["f1"].append(float(seg["f1"]))
                s["f2"].append(float(seg["f2"]))

        if not samples:
            raise CommandError(
                f"Keine referenz-markierten Aufnahmen für speaker={speaker} "
                "gefunden. In der App bzw. im Admin zuerst Aufnahmen mit "
                "ist_referenz markieren.")

        updated = 0
        for phone in sorted(samples):
            f1s, f2s = samples[phone]["f1"], samples[phone]["f2"]
            n = len(f1s)
            if n < options["min_count"]:
                self.stdout.write(self.style.WARNING(
                    f"/{phone}/: nur {n} Datenpunkt(e) < --min-count "
                    f"{options['min_count']} — übersprungen."))
                continue
            f1_mean, f2_mean = statistics.mean(f1s), statistics.mean(f2s)
            f1_sd = max(statistics.stdev(f1s), SD_FLOOR_F1)
            f2_sd = max(statistics.stdev(f2s), SD_FLOOR_F2)

            old = TargetSegment.objects.filter(phone=phone, speaker=speaker).first()
            old_text = (f"F1 {old.f1_mean:.0f}±{old.f1_sd:.0f}, "
                        f"F2 {old.f2_mean:.0f}±{old.f2_sd:.0f}" if old else "—")
            self.stdout.write(
                f"/{phone}/ ({speaker}, n={n}): {old_text}  →  "
                f"F1 {f1_mean:.0f}±{f1_sd:.0f}, F2 {f2_mean:.0f}±{f2_sd:.0f}")

            if not options["dry_run"]:
                TargetSegment.objects.update_or_create(
                    phone=phone, speaker=speaker,
                    defaults={"f1_mean": round(f1_mean, 1),
                              "f1_sd": round(f1_sd, 1),
                              "f2_mean": round(f2_mean, 1),
                              "f2_sd": round(f2_sd, 1)})
                updated += 1

        prefix = "[dry-run, nichts gespeichert] " if options["dry_run"] else ""
        self.stdout.write(self.style.SUCCESS(
            f"{prefix}{updated} TargetSegment(s) aktualisiert."))
