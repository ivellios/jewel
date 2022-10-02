# Generated by Django 4.1.1 on 2022-10-01 18:00

import django.core.validators
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Genre",
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
                ("name", models.CharField(max_length=100, verbose_name="Name")),
            ],
        ),
        migrations.CreateModel(
            name="Platform",
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
                ("name", models.CharField(max_length=100)),
            ],
        ),
        migrations.CreateModel(
            name="Vendor",
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
                ("name", models.CharField(max_length=100)),
            ],
        ),
        migrations.CreateModel(
            name="Game",
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
                ("title", models.CharField(max_length=255, verbose_name="Title")),
                (
                    "play_priority",
                    models.IntegerField(
                        blank=True,
                        null=True,
                        validators=[
                            django.core.validators.MinValueValidator(0),
                            django.core.validators.MaxValueValidator(10),
                        ],
                        verbose_name="Play Priority",
                    ),
                ),
                (
                    "played",
                    models.BooleanField(default=False, verbose_name="Already Played"),
                ),
                (
                    "controller_support",
                    models.BooleanField(
                        default=False, verbose_name="Has controller support?"
                    ),
                ),
                (
                    "max_players",
                    models.PositiveIntegerField(blank=True, default=1, null=True),
                ),
                ("party_fit", models.BooleanField(default=False)),
                (
                    "review",
                    models.IntegerField(
                        blank=True,
                        null=True,
                        validators=[
                            django.core.validators.MinValueValidator(0),
                            django.core.validators.MaxValueValidator(10),
                        ],
                        verbose_name="Review value / rate",
                    ),
                ),
                (
                    "notes",
                    models.TextField(blank=True, null=True, verbose_name="Notes"),
                ),
                (
                    "price",
                    models.DecimalField(
                        decimal_places=2, max_digits=6, verbose_name="Purchase price"
                    ),
                ),
                ("added", models.DateField()),
                ("genre", models.ManyToManyField(to="games.genre")),
                (
                    "platform",
                    models.ManyToManyField(
                        related_name="games",
                        to="games.platform",
                        verbose_name="Platform",
                    ),
                ),
                (
                    "source",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to="games.vendor",
                    ),
                ),
            ],
        ),
    ]
