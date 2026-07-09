"""Seed für das Vokal-Curriculum (PLAN „Vokal-Curriculum nach dem
Vokaltrapez“): Die 7 Laut-Items bekommen ihre Trapez-Gruppe und eine
Artikulationserklärung (Schema Mund/Zunge/Lippen). Kirsten verfeinert
die Texte und spricht das Referenz-Audio im Admin ein.
"""

from django.db import migrations

# phone → (gruppe, beschreibung)
LAUTE = {
    "iː": ("vorn_ungerundet",
           "Mund fast geschlossen, die Zunge weit vorn und hoch am "
           "Gaumen, die Lippen breit (wie beim Lächeln). Wie in „Sie“."),
    "eː": ("vorn_ungerundet",
           "Mund leicht geöffnet, die Zunge vorn, die Lippen neutral "
           "bis leicht breit. Wie in „Tee“."),
    "yː": ("vorn_gerundet",
           "Zunge genauso vorn und hoch wie bei „ie“ — dabei die "
           "Lippen runden und vorstülpen. Wie in „früh“."),
    "øː": ("vorn_gerundet",
           "Zunge vorn wie bei „ee“ — dabei die Lippen runden. "
           "Wie in „Fön“."),
    "uː": ("hinten_gerundet",
           "Mund fast geschlossen, die Zunge weit hinten, die Lippen "
           "stark gerundet und vorgestülpt. Wie in „Kuh“."),
    "oː": ("hinten_gerundet",
           "Mund halb geöffnet, die Zunge hinten, die Lippen gerundet. "
           "Wie in „Zoo“."),
    "aː": ("hinten_gerundet",
           "Mund weit geöffnet, die Zunge flach unten, die Lippen "
           "neutral. Wie in „Tag“."),
}


def seed(apps, schema_editor):
    Item = apps.get_model("api", "Item")
    for item in Item.objects.filter(kind="laut"):
        phone = (item.focus_segments or [None])[0]
        if phone in LAUTE:
            gruppe, beschreibung = LAUTE[phone]
            item.gruppe = gruppe
            # vorhandene (evtl. von Kirsten editierte) Beschreibung wahren
            if not item.beschreibung:
                item.beschreibung = beschreibung
            item.save(update_fields=["gruppe", "beschreibung"])


def unseed(apps, schema_editor):
    Item = apps.get_model("api", "Item")
    Item.objects.filter(kind="laut").update(gruppe="")


class Migration(migrations.Migration):
    dependencies = [
        ("api", "0010_item_beschreibung_item_gruppe_item_reference_audio"),
    ]
    operations = [migrations.RunPython(seed, unseed)]
