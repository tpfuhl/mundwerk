"""Startdaten: Referenz-Formantwerte + Beispiel-Items für Phase 1.

Die TargetSegments werden aus analysis/reference_formants.py übernommen
(Literatur-Startwerte) und sind danach im Admin kuratierbar — die Migration
ist nur der Ausgangspunkt, nicht die dauerhafte Quelle.

Die Items sind bewusst vokal-dominante Einsilber, weil die Segmentierung
bis zur MFA-Integration den längsten stimmhaften Abschnitt nimmt.
"""

from django.db import migrations

from analysis.reference_formants import TARGETS

ITEMS = [
    ("Sie", "ziː", "iː"),
    ("früh", "fʁyː", "yː"),
    ("Kuh", "kuː", "uː"),
    ("Tee", "teː", "eː"),
    ("Fön", "føːn", "øː"),
    ("Zoo", "tsoː", "oː"),
    ("Tag", "taːk", "aː"),
]


def seed(apps, schema_editor):
    TargetSegment = apps.get_model("api", "TargetSegment")
    Item = apps.get_model("api", "Item")
    for phone, by_speaker in TARGETS.items():
        for speaker, (f1_mean, f1_sd, f2_mean, f2_sd) in by_speaker.items():
            TargetSegment.objects.create(
                phone=phone, speaker=speaker,
                f1_mean=f1_mean, f1_sd=f1_sd, f2_mean=f2_mean, f2_sd=f2_sd)
    for text, ipa, focus in ITEMS:
        Item.objects.create(text=text, ipa=ipa, level="A1", focus_segments=[focus])


def unseed(apps, schema_editor):
    apps.get_model("api", "TargetSegment").objects.all().delete()
    apps.get_model("api", "Item").objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [("api", "0001_initial")]
    operations = [migrations.RunPython(seed, unseed)]
