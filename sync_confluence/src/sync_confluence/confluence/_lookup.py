"""Lookup helpers for pages, folders and immediate-children listings."""

from __future__ import annotations

from typing import Optional

from atlassian import Confluence

from sync_confluence.confluence._constants import _Keys
from sync_confluence.confluence._logging import log, _suppress_atlassian_not_found


def _find_page_under_parent(
    confluence: Confluence,
    space_key: str,
    title: str,
    parent_id: str,
) -> Optional[dict]:
    """Find a page by title, verifying it's under the expected parent.

    Returns ``{"id": str, "version": int, "body": str}`` or ``None``.
    """
    with _suppress_atlassian_not_found():
        page = confluence.get_page_by_title(
            space=space_key,
            title=title,
            expand="version,body.storage,ancestors",
        )
    if not page:
        return None

    ancestors = page.get("ancestors", [])
    if not ancestors:
        return None
    if str(ancestors[-1][_Keys.ID]) != str(parent_id):
        return None

    return {
        _Keys.ID: str(page[_Keys.ID]),
        _Keys.VERSION: page[_Keys.VERSION][_Keys.NUMBER],
        "body": page.get("body", {}).get(_Keys.STORAGE, {}).get(_Keys.VALUE, ""),
    }


def _fetch_child_folder(
    confluence: Confluence, parent_id: str, title: str
) -> Optional[dict]:
    """Return folder info via the child/folder endpoint, or ``None`` if not found."""
    response = (
        confluence.get(
            path=f"rest/api/content/{parent_id}/child/folder",
            params={"limit": 200, "expand": _Keys.VERSION},
        )
        or {}
    )
    for folder_entry in response.get(_Keys.RESULTS, []):
        if folder_entry.get(_Keys.TITLE) == title:
            return {
                _Keys.ID: str(folder_entry[_Keys.ID]),
                _Keys.VERSION: folder_entry[_Keys.VERSION][_Keys.NUMBER],
            }
    return None


def _cql_folder_by_parent(
    confluence: Confluence, space_key: str, title: str, parent_id: str
) -> Optional[dict]:
    """Search for a folder by CQL scoped to parent; returns info or ``None``."""
    cql = (
        f'type=folder AND space.key="{space_key}" '
        f'AND title="{title}" AND parent={parent_id}'
    )
    cql_results = confluence.cql(cql, limit=5) or {}
    for search_entry in cql_results.get(_Keys.RESULTS, []):
        folder_data = search_entry.get("content", search_entry)
        if folder_data.get(_Keys.TITLE) == title:
            return {_Keys.ID: str(folder_data[_Keys.ID]), _Keys.VERSION: 1}
    return None


def _find_folder_by_space_cql(
    confluence: Confluence, space_key: str, title: str
) -> Optional[str]:
    """Search for a folder space-wide by CQL; returns folder_id or ``None``."""
    cql = f'type=folder AND space.key="{space_key}" AND title="{title}"'
    cql_results = confluence.cql(cql, limit=5) or {}
    for search_entry in cql_results.get(_Keys.RESULTS, []):
        folder_data = search_entry.get("content", search_entry)
        if folder_data.get(_Keys.TITLE) == title:
            return str(folder_data[_Keys.ID])
    return None


def _find_folder_under_parent(
    confluence: Confluence,
    space_key: str,
    title: str,
    parent_id: str,
) -> Optional[dict]:
    """Find a Confluence Folder by title under *parent_id*.

    Uses the child-folder endpoint first; falls back to a CQL search when
    that endpoint fails or returns no results, because Confluence Cloud may
    not expose the endpoint for all content types.  Returns
    ``{"id": str, "version": int}`` or ``None``.
    """
    folder: Optional[dict] = None
    try:
        folder = _fetch_child_folder(confluence, parent_id, title)
    except Exception as exc:
        log.debug(
            "child/folder endpoint failed for parent %s (%s); trying CQL fallback",
            parent_id,
            exc,
        )

    if folder:
        return folder

    try:
        folder = _cql_folder_by_parent(confluence, space_key, title, parent_id)
    except Exception as exc:
        log.debug("CQL folder search failed for '%s': %s", title, exc)

    return folder


def _get_child_folders(confluence: Confluence, parent_id: str) -> list[dict]:
    """Return the direct child Confluence Folders under *parent_id*.

    Paginates until all results are fetched.
    """
    child_results: list[dict] = []
    limit = 200
    start = 0
    while True:
        try:
            response = (
                confluence.get(
                    path=f"rest/api/content/{parent_id}/child/folder",
                    params={"limit": limit, "start": start},
                )
                or {}
            )
        except Exception:
            break
        page = response.get(_Keys.RESULTS, [])
        child_results.extend(page)
        if len(page) < limit:
            break
        start += limit
    return child_results


def _list_immediate_children(confluence: Confluence, page_id: str) -> list[dict]:
    """Return pages + folders immediately under *page_id* (best effort)."""
    try:
        pages = confluence.get_child_pages(page_id) or []
    except Exception:
        pages = []
    folders = _get_child_folders(confluence, page_id)
    return list(pages) + list(folders)
