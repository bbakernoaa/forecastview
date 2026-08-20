"""Shared dependencies for API endpoints.

Provides singleton instances of ManifestStore and FieldSelector
that are created once at module load and reused across requests.
"""

from __future__ import annotations

from functools import lru_cache

from backend.app.data.field_selector import FieldSelector
from backend.app.data.kerchunk_store import ManifestStore


@lru_cache(maxsize=1)
def get_manifest_store() -> ManifestStore:
    """Return the singleton ManifestStore instance."""
    return ManifestStore()


# Backward compatibility alias
get_kerchunk_store = get_manifest_store


@lru_cache(maxsize=1)
def get_field_selector() -> FieldSelector:
    """Return the singleton FieldSelector instance."""
    return FieldSelector(store=get_manifest_store())
