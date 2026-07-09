"""Seed der Feedback-Regeln aus den Code-Texten (reference_formants.py).

Für jeden Vokal × Dimension (F1/F2) × Richtung (high/low) eine Zeile,
damit Kirsten im Admin alle Fälle vor sich hat und formulieren kann.
Die Texte folgen dem Mund/Zunge/Lippen-Schema. Danach ist die DB die
kuratierte Quelle; der Code bleibt Fallback.
"""

from django.db import migrations

from analysis.reference_formants import TARGETS, feedback_for


def seed(apps, schema_editor):
    FeedbackRule = apps.get_model("api", "FeedbackRule")
    for phone in TARGETS:
        for dim in ("f1", "f2"):
            for direction in ("high", "low"):
                FeedbackRule.objects.update_or_create(
                    phone=phone, dim=dim, direction=direction,
                    defaults={"text": feedback_for(phone, dim, direction)})


def unseed(apps, schema_editor):
    apps.get_model("api", "FeedbackRule").objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [
        ("api", "0008_feedbackrule"),
    ]
    operations = [migrations.RunPython(seed, unseed)]
