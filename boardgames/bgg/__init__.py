"""BoardGameGeek transport and Jewel-owned normalization boundaries."""

from .adapter import (
    BGGBatchRecord,
    BGGCollectionRecord,
    BGGDetailRecord,
    BGGPlaySessionRecord,
    BGGPlaysRecord,
    normalize_batch_item,
    normalize_collection_item,
    normalize_detail,
    normalize_plays,
)
from .client import DEFAULT_BGG_API_URL, BGGClient
from .errors import (
    BGGAdapterError,
    BGGCredentialMissingError,
    BGGNetworkError,
    BGGNotFoundError,
)
from .repository import BGGExpansionRecord, BGGRepository, BGGRepositoryProtocol

__all__ = [
    # Transport and repository
    "BGGClient",
    "DEFAULT_BGG_API_URL",
    "BGGRepository",
    "BGGRepositoryProtocol",
    # Records
    "BGGBatchRecord",
    "BGGCollectionRecord",
    "BGGDetailRecord",
    "BGGExpansionRecord",
    "BGGPlaySessionRecord",
    "BGGPlaysRecord",
    # Normalizers
    "normalize_batch_item",
    "normalize_collection_item",
    "normalize_detail",
    "normalize_plays",
    # Errors
    "BGGAdapterError",
    "BGGCredentialMissingError",
    "BGGNetworkError",
    "BGGNotFoundError",
]
