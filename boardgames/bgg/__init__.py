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
from .client import DEFAULT_BGG_API_URL, BGGClient
from .errors import (
    BGGAdapterError,
    BGGCredentialMissingError,
    BGGNetworkError,
    BGGNotFoundError,
)

__all__ = [
    # Adapter
    "BGGAdapter",
    "BGGClient",
    "DEFAULT_BGG_API_URL",
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
