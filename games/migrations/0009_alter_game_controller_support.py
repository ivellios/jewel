# Generated by Django 4.1.1 on 2022-10-01 20:56

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("games", "0008_rename_genre_game_genres"),
    ]

    operations = [
        migrations.AlterField(
            model_name="game",
            name="controller_support",
            field=models.BooleanField(
                blank=True,
                default=False,
                null=True,
                verbose_name="Has controller support?",
            ),
        ),
    ]
