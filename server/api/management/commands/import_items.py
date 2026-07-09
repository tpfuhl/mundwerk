"""Übungswörter aus einer CSV-Datei importieren (Kuratierung durch Kirsten).

Erwartete Spalten (Kopfzeile erforderlich):
    text   — das Wort/der Satz, z. B. "schön"
    ipa    — IPA-Transkription, z. B. "ʃøːn"
    level  — GER-Niveau A1..C2
    focus  — Fokus-Laut(e) in IPA, mehrere durch Leerzeichen: "øː n"

Optionale Spalten (PLAN „Segmentdiagnose“):
    kind      — laut | wort | satz (Default: wort); "laut" = isoliert
                gehaltener Laut, wird ohne Alignment analysiert
    pron      — Soll-Lautung in MFA-Phonen, z. B. "f ʁ yː"
    varianten — typische Fehlaussprachen, durch | getrennt:
                "f l yː | f k yː | f yː" (braucht pron; didaktische
                Hinweise pro Variante werden im Admin gepflegt)

Trennzeichen Komma oder Semikolon (deutsches Excel/LibreOffice) werden
automatisch erkannt, ebenso ein UTF-8-BOM. Existiert ein Wort bereits
(gleicher text), wird es aktualisiert statt dupliziert.

    manage.py import_items wortliste.csv [--dry-run]
"""

import csv

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from api.models import Item, TargetSegment

REQUIRED = {"text", "ipa", "level", "focus"}
LEVELS = {"A1", "A2", "B1", "B2", "C1", "C2"}
KINDS = {"laut", "wort", "satz"}


class Command(BaseCommand):
    help = "Importiert/aktualisiert Übungswörter aus einer CSV-Datei."

    def add_arguments(self, parser):
        parser.add_argument("csv_path")
        parser.add_argument("--dry-run", action="store_true",
                            help="nur prüfen und berichten, nichts speichern")

    def handle(self, *args, **options):
        try:
            f = open(options["csv_path"], encoding="utf-8-sig", newline="")
        except OSError as e:
            raise CommandError(f"Datei nicht lesbar: {e}")

        with f:
            sample = f.read(2048)
            f.seek(0)
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=",;")
            except csv.Error:
                dialect = csv.excel
            reader = csv.DictReader(f, dialect=dialect)

            header = {h.strip().lower() for h in reader.fieldnames or []}
            missing = REQUIRED - header
            if missing:
                raise CommandError(
                    f"Spalte(n) fehlen: {', '.join(sorted(missing))} — "
                    f"gefunden: {', '.join(sorted(header))}")

            created = updated = 0
            focus_phones = set()
            errors = []
            with transaction.atomic():
                for lineno, row in enumerate(reader, start=2):
                    row = {k.strip().lower(): (v or "").strip()
                           for k, v in row.items() if k}
                    if not any(row.values()):
                        continue  # Leerzeile
                    text, ipa = row["text"], row["ipa"]
                    level, focus = row["level"].upper(), row["focus"].split()
                    if not (text and ipa and focus):
                        errors.append(f"Zeile {lineno}: text/ipa/focus unvollständig")
                        continue
                    if level not in LEVELS:
                        errors.append(f"Zeile {lineno}: unbekanntes Niveau „{row['level']}“")
                        continue
                    focus_phones.update(focus)
                    defaults = {"ipa": ipa, "level": level,
                                "focus_segments": focus}
                    # Optionale Spalten überschreiben nur, wenn sie in der
                    # CSV vorhanden sind — sonst bleiben Admin-Werte stehen.
                    if "kind" in header:
                        kind = (row.get("kind") or "wort").lower()
                        if kind not in KINDS:
                            errors.append(f"Zeile {lineno}: unbekannter Typ "
                                          f"„{row['kind']}“ (laut|wort|satz)")
                            continue
                        defaults["kind"] = kind
                    if "pron" in header:
                        defaults["mfa_pron"] = " ".join(row.get("pron", "").split())
                    if "varianten" in header:
                        varianten = [" ".join(v.split()) for v
                                     in row.get("varianten", "").split("|")
                                     if v.strip()]
                        if varianten and not (row.get("pron") or "").strip():
                            errors.append(f"Zeile {lineno}: varianten ohne "
                                          "pron (Soll-Lautung fehlt)")
                            continue
                        # Im Admin gepflegte Hinweise zu gleichem pron erhalten
                        existing = Item.objects.filter(text=text).first()
                        hints = dict(existing.variant_list()) if existing else {}
                        defaults["error_variants"] = [
                            {"pron": v, "hinweis": hints[v]}
                            if hints.get(v) else {"pron": v}
                            for v in varianten]
                    _, was_created = Item.objects.update_or_create(
                        text=text, defaults=defaults)
                    created += was_created
                    updated += not was_created

                if errors:
                    raise CommandError(
                        "Import abgebrochen (nichts gespeichert):\n  "
                        + "\n  ".join(errors))
                if options["dry_run"]:
                    transaction.set_rollback(True)

        known = set(TargetSegment.objects.values_list("phone", flat=True))
        unknown = sorted(focus_phones - known)
        if unknown:
            self.stdout.write(self.style.WARNING(
                f"Hinweis: keine Referenzwerte für {', '.join(unknown)} — "
                "diese Laute sind erst analysierbar, wenn TargetSegments "
                "dafür angelegt sind (Admin oder reference_formants.py)."))

        prefix = "[dry-run, nichts gespeichert] " if options["dry_run"] else ""
        self.stdout.write(self.style.SUCCESS(
            f"{prefix}{created} neu, {updated} aktualisiert."))
