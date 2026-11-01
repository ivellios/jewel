"""Explicit adapter errors — Jewel-owned hierarchy."""

from __future__ import annotations


class BGGAdapterError(Exception):
    """Base error for all BGG adapter failures."""


class BGGCredentialMissingError(BGGAdapterError):
    """Raised when required BGG credentials (access token) are missing."""


class BGGNotFoundError(BGGAdapterError):
    """Raised when the BGG API indicates the requested resource was not found."""


class BGGNetworkError(BGGAdapterError):
    """Raised when a network-level or API-level error occurs (timeout, retry, etc.)."""
