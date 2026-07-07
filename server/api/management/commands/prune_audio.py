"""Sicherheitsnetz zum Audio-Lebenszyklus: löscht Audiodateien alter
Aufnahmen, die der Sofort-Löschung entgangen sind (z. B. Uploads, deren
Analyse abgebrochen ist). Ergebnisse bleiben erhalten.

Gedacht für einen täglichen Cronjob:
    manage.py prune_audio --days 30
Korpus-Aufnahmen (Gruppe "korpus") werden nur mit --include-korpus erfasst.
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from api.models import Recording


class Command(BaseCommand):
    help = "Löscht Audiodateien von Aufnahmen älter als --days (Ergebnisse bleiben)."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=30)
        parser.add_argument("--include-korpus", action="store_true",
                            help="auch Aufnahmen der Korpus-Gruppe löschen")

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(days=options["days"])
        qs = (Recording.objects.filter(created_at__lt=cutoff)
              .exclude(audio=""))
        if not options["include_korpus"]:
            qs = qs.exclude(user__groups__name="korpus")
        count = 0
        for recording in qs:
            recording.audio.delete(save=True)
            count += 1
        self.stdout.write(f"{count} Audiodatei(en) gelöscht.")
