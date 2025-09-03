import uuid

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from games.signals import platform_added_for_game


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
    def with_active_platforms(self):
        """Return games that have at least one non-deleted platform"""
        return self.filter(platforms_meta_data__deleted=False).distinct()

    def orphaned(self):
        """Return games with no active platforms (all platforms soft-deleted)"""
        # Games that either have no platforms or all platforms are deleted
        return self.exclude(platforms_meta_data__deleted=False)


class GameManager(models.Manager):
    def get_queryset(self):
        """Override to exclude orphaned games by default"""
        return (
            super().get_queryset().filter(platforms_meta_data__deleted=False).distinct()
        )

    def all_with_orphaned(self):
        """Return all games including orphaned ones"""
        return super().get_queryset()

    def orphaned_only(self):
        """Return only orphaned games (no platforms or all platforms deleted)"""
        return GameQuerySet(self.model, using=self._db).orphaned()


class Game(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, verbose_name="Game title")
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
        return self.name

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
    vendor = models.ForeignKey(Vendor, on_delete=models.SET_NULL, null=True, blank=True)
    deleted = models.BooleanField(default=False, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.game.name} on {self.platform.name}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        platform_added_for_game.send(sender=self.__class__, instance=self)

    def soft_delete(self):
        """Mark this game-platform relationship as deleted"""
        self.deleted = True
        self.deleted_at = timezone.now()
        self.save(update_fields=["deleted", "deleted_at"])

    def restore(self):
        """Restore this game-platform relationship"""
        self.deleted = False
        self.deleted_at = None
        self.save(update_fields=["deleted", "deleted_at"])
