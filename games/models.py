import uuid

from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models


class NamedModel(models.Model):
    name = models.CharField(max_length=100)

    class Meta:
        abstract = True

    def __str__(self):
        return self.name


class Vendor(NamedModel, models.Model):
    pass


class Platform(NamedModel, models.Model):
    pass


class Genre(NamedModel, models.Model):
    pass


class GameQuerySet(models.QuerySet):
    pass


class GameManager(models.Manager):
    pass


class Game(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255, verbose_name="Title")
    platforms = models.ManyToManyField(
        Platform,
        verbose_name="Platform",
        related_name="games",
        through="GameOnPlatform",
        blank=True,
    )
    play_priority = models.IntegerField(
        verbose_name="Play Priority",
        validators=[
            MinValueValidator(0),
            MaxValueValidator(10),
        ],
        null=True,
        blank=True,
    )
    played = models.BooleanField(
        verbose_name="Already Played", default=False, null=True
    )
    controller_support = models.BooleanField(
        verbose_name="Has controller support?", default=False, null=True, blank=True
    )
    max_players = models.PositiveIntegerField(default=1, null=True, blank=True)
    party_fit = models.BooleanField(default=False, null=True, blank=True)
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
    genres = models.ManyToManyField(Genre, blank=True)

    objects = GameManager.from_queryset(GameQuerySet)()

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        creating = not self.pk
        super().save(*args, **kwargs)
        if creating:
            # detect and fill data automatically
            pass


class GameOnPlatform(models.Model):
    game = models.ForeignKey(
        Game, on_delete=models.CASCADE, related_name="platforms_meta_data"
    )
    platform = models.ForeignKey(
        Platform, on_delete=models.CASCADE, related_name="games_meta_data"
    )
    added = models.DateField(null=True, blank=True)
    identifier = models.CharField(
        verbose_name="ID in the platform for generating URLs",
        max_length=255,
        blank=True,
        null=True,
    )
    price = models.DecimalField(
        verbose_name="Purchase price",
        decimal_places=2,
        max_digits=6,
        blank=True,
        null=True,
    )
    added = models.DateField(null=True, blank=True)
    source = models.ForeignKey(Vendor, on_delete=models.SET_NULL, null=True, blank=True)

