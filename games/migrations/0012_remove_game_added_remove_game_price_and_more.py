# Generated by Django 4.1.1 on 2022-10-02 13:14

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("games", "0011_alter_game_genres_alter_game_platforms_and_more"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="game",
            name="added",
        ),
        migrations.RemoveField(
            model_name="game",
            name="price",
        ),
        migrations.RemoveField(
            model_name="game",
            name="source",
        ),
        migrations.AddField(
            model_name="gameonplatform",
            name="price",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                max_digits=6,
                null=True,
                verbose_name="Purchase price",
            ),
        ),
        migrations.AddField(
            model_name="gameonplatform",
            name="source",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="games.vendor",
            ),
        ),
    ]
