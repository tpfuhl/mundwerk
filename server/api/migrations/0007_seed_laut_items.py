"""Seed für die Segmentdiagnose (PLAN, Schritt 1+2):

- Die sieben Langvokale als isolierte Laut-Items (kind="laut") — der
  didaktische Einstieg „Welche Laute kann ich schon?“. Analyse ohne
  Alignment (Auto-Segmentierung), daher sofort funktionsfähig.
- Das Seed-Wort „früh“ bekommt Soll-Lautung + Fehlervarianten als
  Arbeitsbeispiel für das Fehlerhypothesen-Alignment (Kirstens Fälle
  „flüh“ und „fküh“). Kuratierung/Erweiterung im Admin.
"""

from django.db import migrations

LAUTE = [  # (Anzeige-Text, IPA)
    ("ie", "iː"),
    ("üh", "yː"),
    ("uh", "uː"),
    ("ee", "eː"),
    ("öh", "øː"),
    ("oh", "oː"),
    ("ah", "aː"),
]


def seed(apps, schema_editor):
    Item = apps.get_model("api", "Item")
    for text, ipa in LAUTE:
        Item.objects.update_or_create(
            text=text, kind="laut",
            defaults={"ipa": ipa, "level": "A1", "focus_segments": [ipa]})
    Item.objects.filter(text="früh", kind="wort").update(
        mfa_pron="f ʁ yː",
        error_variants=[
            {"pron": "f l yː",
             "hinweis": "Das ‚r‘ klang wie ein ‚l‘. Das deutsche R in "
                        "„früh“ wird hinten im Rachen gebildet — die "
                        "Zungenspitze bleibt unten."},
            {"pron": "f k yː",
             "hinweis": "Vor dem ‚ü‘ war ein k-artiger Laut zu hören. "
                        "Das R weich und ohne Verschluss sprechen, wie "
                        "ein sanftes Gurgeln."},
            {"pron": "f yː",
             "hinweis": "Das ‚r‘ hat gefehlt — „früh“ hat drei Laute: "
                        "f – r – üh."},
        ])


def unseed(apps, schema_editor):
    Item = apps.get_model("api", "Item")
    Item.objects.filter(kind="laut",
                        text__in=[t for t, _ in LAUTE]).delete()
    Item.objects.filter(text="früh", kind="wort").update(
        mfa_pron="", error_variants=[])


class Migration(migrations.Migration):
    dependencies = [
        ("api", "0006_item_error_variants_item_kind_item_mfa_pron"),
    ]
    operations = [migrations.RunPython(seed, unseed)]
