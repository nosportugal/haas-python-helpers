"""Build a ``{source_path: page_id}`` mapping for rename detection."""

from __future__ import annotations

from typing import Optional

from atlassian import Confluence

from sync_confluence.confluence._constants import _Keys
from sync_confluence.confluence._logging import log
from sync_confluence.confluence._properties import _get_source_path_property


def _fetch_child_page_batch(
    confluence: Confluence, parent_id: str, limit: int, start: int
) -> Optional[dict]:
    """Fetch one batch of child pages; returns ``None`` on error."""
    try:
        return (
            confluence.get(
                path=f"rest/api/content/{parent_id}/child/page",
                params={"limit": limit, "start": start},
            )
            or {}
        )
    except Exception as exc:
        log.debug(
            "Could not fetch child pages for parent %s to build source path map: %s",
            parent_id,
            exc,
        )
        return None


def _register_source_path(
    path_map: dict[str, str], source_path: str, page_id: str
) -> None:
    """Add ``source_path → page_id`` to *path_map*, warning on duplicates."""
    if source_path in path_map:
        log.warning(
            "Duplicate source_path '%s' on pages id=%s and id=%s; "
            "keeping id=%s for rename detection",
            source_path,
            path_map.get(source_path),
            page_id,
            path_map.get(source_path),
        )
        return
    path_map[source_path] = page_id


def _ingest_page_batch(
    confluence: Confluence, pages: list[dict], path_map: dict[str, str]
) -> None:
    """For each page, look up its source_path property and register it."""
    for page in pages:
        page_id = str(page[_Keys.ID])
        source_path = _get_source_path_property(confluence, page_id)
        if source_path:
            _register_source_path(path_map, source_path, page_id)


def build_source_path_map(
    confluence: Confluence,
    parent_id: str,
) -> dict[str, str]:
    """Return a ``{source_path: page_id}`` mapping for all managed child pages
    under *parent_id* that have the ``sync_confluence_source_path`` property
    set.  Used for rename detection: when a file's source path is in the
    mapping under a different title, the existing page is updated in-place
    instead of creating a duplicate.  Paginates through all children.
    """
    path_map: dict[str, str] = {}
    limit = 200
    start = 0
    while True:
        response = _fetch_child_page_batch(confluence, parent_id, limit, start)
        if response is None:
            break
        pages = response.get(_Keys.RESULTS, [])
        _ingest_page_batch(confluence, pages, path_map)
        if len(pages) < limit:
            break
        start += limit
    return path_map
