from django.db import migrations, models


def keep_existing_sites_active(apps, schema_editor):
    Site = apps.get_model("core", "Site")
    Site.objects.using(schema_editor.connection.alias).update(actif=True)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="site",
            name="actif",
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(keep_existing_sites_active, migrations.RunPython.noop),
    ]
