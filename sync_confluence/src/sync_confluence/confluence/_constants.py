"""Constants grouped to keep the module member count under WPS202.

The :class:`_Keys` and :class:`PageSyncAction` containers hold the Confluence API
response field names and the upsert result actions, respectively.  Using
classes keeps the related names together and counts as a single module
member each.
"""

from __future__ import annotations


class _Keys:
    """Confluence API response field keys."""

    ID = "id"
    VERSION = "version"
    NUMBER = "number"
    STORAGE = "storage"
    VALUE = "value"
    TITLE = "title"
    RESULTS = "results"


class PageSyncAction:
    """Page sync action values (created, updated, unchanged, skipped)."""

    CREATED = "created"
    UPDATED = "updated"
    UNCHANGED = "unchanged"
    SKIPPED = "skipped"


# Dry-run placeholder page id returned instead of a real Confluence id.
DRY_RUN_PAGE_ID = "DRY-RUN"
_HASH_PROPERTY_KEY = "sync_confluence_hash"
_SOURCE_PATH_PROPERTY_KEY = "sync_confluence_source_path"
_APPEARANCE_PUBLISHED_KEY = "content-appearance-published"
_APPEARANCE_DRAFT_KEY = "content-appearance-draft"
