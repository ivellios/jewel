# Generated by Django 4.1.1 on 2022-10-01 18:17

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("games", "0002_remove_game_platform_gameonplatform_game_platforms"),
    ]

    operations = [
        migrations.AlterField(
            model_name="gameonplatform",
            name="added",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="gameonplatform",
            name="identifier",
            field=models.CharField(
                blank=True,
                max_length=255,
                null=True,
                verbose_name="ID in the platform for generating URLs",
            ),
        ),
    ]
