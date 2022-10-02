# Generated by Django 4.1.1 on 2022-10-01 18:16

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("games", "0001_initial"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="game",
            name="platform",
        ),
        migrations.CreateModel(
            name="GameOnPlatform",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("added", models.DateField()),
                (
                    "identifier",
                    models.CharField(
                        max_length=255,
                        verbose_name="ID in the platform for generating URLs",
                    ),
                ),
                (
                    "game",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="games.game"
                    ),
                ),
                (
                    "platform",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="games.platform"
                    ),
                ),
            ],
        ),
        migrations.AddField(
            model_name="game",
            name="platforms",
            field=models.ManyToManyField(
                related_name="games",
                through="games.GameOnPlatform",
                to="games.platform",
                verbose_name="Platform",
            ),
        ),
    ]
