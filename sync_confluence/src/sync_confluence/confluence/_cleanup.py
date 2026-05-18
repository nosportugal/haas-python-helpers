"""Delete orphaned pages/folders that no longer correspond to source files."""

from __future__ import annotations

from typing import Optional

from atlassian import Confluence

from sync_confluence.confluence._constants import _Keys
from sync_confluence.confluence._logging import log
from sync_confluence.confluence._lookup import _list_immediate_children
from sync_confluence.confluence._properties import (
    _get_source_path_property,
    _page_has_label,
)
from sync_confluence.confluence._types import DeleteOrphansRequest


def _collect_children(confluence: Confluence, page_id: str) -> list[dict]:
    """Recursively collect all descendant pages and folders under *page_id*.

    Returns a flat list of ``{"id", "title"}`` dicts ordered leaves-first
    (safe for bottom-up deletion).
    """
    collection: list[dict] = []
    for child in _list_immediate_children(confluence, page_id):
        child_id = str(child[_Keys.ID])
        collection.extend(_collect_children(confluence, child_id))
        collection.append({_Keys.ID: child_id, _Keys.TITLE: child[_Keys.TITLE]})
    return collection


def _is_kept_by_path(
    confluence: Confluence, orphan_id: str, expected_paths: Optional[set[str]]
) -> Optional[str]:
    """Return source_path string if the page should be kept, else None."""
    if expected_paths is None:
        return None
    source_path = _get_source_path_property(confluence, orphan_id)
    if source_path is None or source_path not in expected_paths:
        return None
    return source_path


def _is_orphan_eligible(
    confluence: Confluence, page: dict, request: DeleteOrphansRequest
) -> bool:
    """True if *page* is an orphan and the caller should delete it."""
    orphan_title = page[_Keys.TITLE]
    orphan_id = page[_Keys.ID]
    if orphan_title in request.expected_titles:
        return False
    kept_path = _is_kept_by_path(confluence, orphan_id, request.expected_paths)
    if kept_path is not None:
        log.debug(
            "Keeping '%s' (id=%s) — source path '%s' still exists",
            orphan_title,
            orphan_id,
            kept_path,
        )
        return False
    if request.managed_by_label and not _page_has_label(
        confluence, orphan_id, request.managed_by_label
    ):
        log.debug("Skipping non-managed page: '%s' (id=%s)", orphan_title, orphan_id)
        return False
    return True


def _delete_one_orphan(
    confluence: Confluence, orphan_id: str, orphan_title: str, dry_run: bool
) -> None:
    if dry_run:
        log.info("[DRY-RUN] Would delete orphan: '%s' (id=%s)", orphan_title, orphan_id)
        return
    confluence.remove_page(orphan_id)
    log.info("Deleted orphan: '%s' (id=%s)", orphan_title, orphan_id)


def delete_orphans(confluence: Confluence, request: DeleteOrphansRequest) -> int:
    """Delete pages under ``request.root_page_id`` whose titles are not in
    ``request.expected_titles`` and whose source paths are not in
    ``request.expected_paths``.

    Deletes bottom-up to avoid cascade issues.  Returns the count of deleted
    pages.  When ``request.managed_by_label`` is set, only pages that carry
    that label are eligible for deletion.  When ``request.expected_paths`` is
    set, each candidate's ``sync_confluence_source_path`` page property is
    checked before deletion — a page whose stored source path is still in
    *expected_paths* is kept even if its title changed (rename detection).
    """
    all_pages = _collect_children(confluence, request.root_page_id)
    deleted = 0
    for page in all_pages:
        if not _is_orphan_eligible(confluence, page, request):
            continue
        _delete_one_orphan(
            confluence, page[_Keys.ID], page[_Keys.TITLE], request.dry_run
        )
        deleted += 1
    return deleted
