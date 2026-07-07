"""Gruppe "korpus": Mitglieder haben zugestimmt, dass ihre Aufnahmen für
die Kalibrierung der Referenzformanten aufbewahrt werden. Für alle anderen
wird das Audio direkt nach der Analyse gelöscht (nur das Ergebnis bleibt).
"""

from django.db import migrations


def create_group(apps, schema_editor):
    apps.get_model("auth", "Group").objects.get_or_create(name="korpus")


def drop_group(apps, schema_editor):
    apps.get_model("auth", "Group").objects.filter(name="korpus").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("api", "0002_seed_data"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]
    operations = [migrations.RunPython(create_group, drop_group)]
