from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class CollectionItem(models.Model):
    name = models.CharField(max_length=255, verbose_name="Game title")
    played = models.BooleanField(
        verbose_name="Already Played", default=False, null=True
    )
    review = models.IntegerField(
        verbose_name="Review value / rate",
        validators=[
            MinValueValidator(0),
            MaxValueValidator(10),
        ],
        null=True,
        blank=True,
    )
    notes = models.TextField(verbose_name="Notes", null=True, blank=True)
    play_priority = models.IntegerField(
        verbose_name="Play Priority",
        validators=[
            MinValueValidator(0),
            MaxValueValidator(10),
        ],
        null=True,
        blank=True,
    )
    min_players = models.PositiveIntegerField(default=1, null=True, blank=True)
    max_players = models.PositiveIntegerField(default=1, null=True, blank=True)

    class Meta:
        abstract = True
