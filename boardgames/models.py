"""BoardGameGeek canonical metadata and sync-run lifecycle models."""

from django.core.validators import MinValueValidator
from django.db import models


class BGGMetadata(models.Model):
    """Canonical BoardGameGeek metadata, one row per BGG ID.

    Stores only the canonical metadata fields from BGG. Local-copy fields
    and application-specific data are explicitly out of scope.

    The ``bgg_id`` field is unique and serves as the authoritative
    identifier for deduplication at the database level.

    Source fields (name, year, publishers, designers, mechanics, etc.)
    are all nullable because partial fetches may omit values.
    """

    bgg_id = models.IntegerField(unique=True, db_index=True)
    name = models.CharField(max_length=500, null=True, blank=True)
    yearpublished = models.PositiveIntegerField(null=True, blank=True)
    minplayers = models.PositiveIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
    )
    maxplayers = models.PositiveIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
    )
    playingtime = models.PositiveIntegerField(null=True, blank=True)
    comment = models.TextField(null=True, blank=True)
    thumbnail = models.URLField(max_length=2000, null=True, blank=True)
    image = models.URLField(max_length=2000, null=True, blank=True)
    publishers = models.TextField(null=True, blank=True)
    designers = models.TextField(null=True, blank=True)
    mechanics = models.TextField(null=True, blank=True)
    categories = models.TextField(null=True, blank=True)

    class Meta:
        ordering = ["bgg_id"]
        verbose_name = "BGG metadata"
        verbose_name_plural = "BGG metadata"

    def __str__(self) -> str:
        return f"BGG#{self.bgg_id}"


class BGGExpansion(models.Model):
    """Explicit BoardGameGeek expansion relationship.

    Stores the BGG ``extends`` link between games so that an expansion
    can reference multiple base games and the relationship is
    deduplicated and self-link-safe.

    One canonical row per (expansion, parent) pair.  Expansion games
    that also appear as ``parent`` support chain links (expansion of
    expansion).  No other table is touched.
    """

    expansion = models.ForeignKey(
        "BGGMetadata",
        on_delete=models.CASCADE,
        related_name="expansions_of",
        db_constraint=True,
        help_text="The game that is the expansion.",
    )
    parent = models.ForeignKey(
        "BGGMetadata",
        on_delete=models.CASCADE,
        related_name="is_expanded_by",
        db_constraint=True,
        help_text="The base game that the expansion extends.",
    )
    # BGG expansion-type values (see BGG API documentation).
    # Common values: "boardgameexpansion", "boardgamesubdirectory".
    exp_type = models.CharField(
        max_length=40,
        null=True,
        blank=True,
        help_text="BGG expansion type (e.g. 'boardgameexpansion').",
    )
    order = models.SmallIntegerField(
        default=0,
        help_text="Order among multiple base games for the same expansion.",
    )

    class Meta:
        ordering = ["expansion__bgg_id", "order"]
        constraints = [
            models.UniqueConstraint(
                fields=["expansion", "parent"],
                name="boardgames_unique_expansion_parent",
            ),
            models.CheckConstraint(
                check=~models.Q(expansion=models.F("parent")),
                name="boardgames_no_self_link",
                violation_error_message="An expansion cannot link to itself.",
            ),
        ]

    def __str__(self) -> str:
        return f"BGG#{self.expansion.bgg_id} -> BGG#{self.parent.bgg_id}"


class BGGSyncRunStatus(models.TextChoices):
    """Lifecycle status for a BGG synchronization run."""

    FULL = "full", "Complete full fetch completed successfully"
    PARTIAL = "partial", "Fetch completed with some errors"
    FAILED = "failed", "Fetch failed before meaningful progress"


class BGGSyncRun(models.Model):
    """Tracks the lifecycle of a single BGG synchronization operation.

    Persists the full/partial/failed status, whether a complete fetch
    succeeded, per-run counters, bounded per-item error text, timestamps,
    and lightweight diagnostics. Does not store raw payloads.
    """

    status = models.CharField(
        max_length=10,
        choices=BGGSyncRunStatus.choices,
        default=BGGSyncRunStatus.FAILED,
        db_index=True,
    )
    fetch_successful = models.BooleanField(default=False)
    items_total = models.PositiveIntegerField(default=0)
    items_fetched = models.PositiveIntegerField(default=0)
    items_failed = models.PositiveIntegerField(default=0)
    error_messages = models.TextField(
        null=True,
        blank=True,
        help_text="Bounded, user-friendly per-item errors (truncated).",
    )
    diagnostics = models.TextField(
        null=True,
        blank=True,
        help_text="Lightweight diagnostics without raw payload.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "BGG sync run"
        verbose_name_plural = "BGG sync runs"

    def __str__(self) -> str:
        return f"BGGSyncRun#{self.pk} ({self.status})"
