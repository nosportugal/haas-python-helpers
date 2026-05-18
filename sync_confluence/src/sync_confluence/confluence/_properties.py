"""Page properties and labels: hashes, source paths, and managed-by labels."""

from __future__ import annotations

import hashlib
from typing import Optional

from atlassian import Confluence

from sync_confluence.confluence._constants import (
    _HASH_PROPERTY_KEY,
    _SOURCE_PATH_PROPERTY_KEY,
    _Keys,
)
from sync_confluence.confluence._logging import log


def _content_hash(body: str) -> str:
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _fetch_hash_prop_value(confluence: Confluence, page_id: str) -> Optional[str]:
    """Return the stored content hash for *page_id*, or ``None`` if absent."""
    prop = confluence.get_page_property(page_id, _HASH_PROPERTY_KEY)
    return prop[_Keys.VALUE] if prop and _Keys.VALUE in prop else None


def _upsert_page_property(
    confluence: Confluence, page_id: str, key: str, prop_value: str
) -> None:
    """Create or update a page property, handling versioning for updates."""
    try:
        prop = confluence.get_page_property(page_id, key)
    except Exception:
        prop = None  # Property does not exist yet \u2014 will be created below

    if prop and _Keys.VERSION in prop:
        version = prop.get(_Keys.VERSION, {}).get(_Keys.NUMBER, 1)
        response = confluence.request(
            method="PUT",
            path=f"rest/api/content/{page_id}/property/{key}",
            data={
                "key": key,
                _Keys.VALUE: prop_value,
                _Keys.VERSION: {"number": version + 1},
            },
            advanced_mode=True,
        )
    else:
        response = confluence.request(
            method="POST",
            path=f"rest/api/content/{page_id}/property",
            data={"key": key, _Keys.VALUE: prop_value},
            advanced_mode=True,
        )
    response.raise_for_status()


def _try_property_set(
    confluence: Confluence, page_id: str, key: str, prop_value: str, what: str
) -> None:
    """Best-effort property set, logging failures without raising."""
    try:
        _upsert_page_property(confluence, page_id, key, prop_value)
    except Exception as exc:
        log.warning("Could not set %s property for page id=%s: %s", what, page_id, exc)


def _apply_label(confluence: Confluence, page_id: str, label: str) -> None:
    """Attach *label* to *page_id*; idempotent."""
    confluence.set_page_label(page_id, label)


def _page_has_label(confluence: Confluence, page_id: str, label: str) -> bool:
    """Return ``True`` if *page_id* carries *label*.  Works for pages and folders."""
    page_labels: dict = {}
    try:
        page_labels = confluence.get(path=f"rest/api/content/{page_id}/label") or {}
    except Exception:
        return False
    entries = page_labels.get(_Keys.RESULTS, [])
    return any(entry["name"] == label for entry in entries)


def _get_source_path_property(confluence: Confluence, page_id: str) -> Optional[str]:
    """Fetch the ``sync_confluence_source_path`` property, or ``None`` if absent."""
    try:
        prop = confluence.get_page_property(page_id, _SOURCE_PATH_PROPERTY_KEY)
    except Exception as exc:
        log.debug(
            "Failed to fetch page property '%s' for page id=%s: %s",
            _SOURCE_PATH_PROPERTY_KEY,
            page_id,
            exc,
        )
        return None
    return prop[_Keys.VALUE] if prop and _Keys.VALUE in prop else None
