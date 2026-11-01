"""BoardGameGeek adapter — Jewel-owned normalisation layer."""

from .adapter import (
    BGGAdapter,
    BGGBatchRecord,
    BGGCollectionRecord,
    BGGDetailRecord,
    BGGExpansionRecord,
    BGGPlaysRecord,
    BGGRatingRecord,
)
from .errors import (
    BGGAdapterError,
    BGGCredentialMissingError,
    BGGNetworkError,
    BGGNotFoundError,
)

__all__ = [
    # Adapter
    "BGGAdapter",
    # Records
    "BGGBatchRecord",
    "BGGCollectionRecord",
    "BGGDetailRecord",
    "BGGExpansionRecord",
    "BGGPlaysRecord",
    "BGGRatingRecord",
    # Errors
    "BGGAdapterError",
    "BGGCredentialMissingError",
    "BGGNetworkError",
    "BGGNotFoundError",
]
