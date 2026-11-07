"""Dry-run simulation of :func:`sync_confluence.confluence.upsert_page`."""

from __future__ import annotations

from atlassian import Confluence

from sync_confluence.confluence._constants import DRY_RUN_PAGE_ID, PageSyncAction, _Keys
from sync_confluence.confluence._logging import log
from sync_confluence.confluence._lookup import find_page_under_parent
from sync_confluence.confluence._page_metadata import (
    _log_dry_run_metadata,
    _rename_target,
)
from sync_confluence.confluence._properties import (
    _content_hash,
    _fetch_hash_prop_value,
)
from sync_confluence.confluence._types import PageUpsertRequest


def _dry_run_existing_page(
    confluence: Confluence, request: PageUpsertRequest, existing_id: str
) -> tuple[str, str]:
    """Report ``unchanged`` or ``updated`` for an existing page, as a live run would."""
    try:
        prop_val = _fetch_hash_prop_value(confluence, existing_id)
    except Exception as exc:
        log.warning(
            "Could not fetch hash property for page id=%s (%s); assuming update",
            existing_id,
            exc,
        )
        prop_val = None
    if prop_val == _content_hash(request.body):
        log.debug("[DRY-RUN] Unchanged: '%s' (id=%s)", request.title, existing_id)
        return (existing_id, PageSyncAction.UNCHANGED)
    log.info("[DRY-RUN] Would update '%s' (id=%s)", request.title, existing_id)
    _log_dry_run_metadata(request)
    return (existing_id, PageSyncAction.UPDATED)


def _upsert_page_dry_run(
    confluence: Confluence, request: PageUpsertRequest
) -> tuple[str, str]:
    """Simulate :func:`upsert_page` for dry-run mode."""
    existing = find_page_under_parent(
        confluence, request.space_key, request.title, request.parent_id
    )
    if existing:
        return _dry_run_existing_page(confluence, request, existing[_Keys.ID])
    rename_id = _rename_target(request)
    if rename_id is not None:
        log.info(
            "[DRY-RUN] Would rename page id=%s to '%s' and update content",
            rename_id,
            request.title,
        )
        _log_dry_run_metadata(request)
        return (DRY_RUN_PAGE_ID, PageSyncAction.UPDATED)
    _log_dry_run_metadata(request)
    return (DRY_RUN_PAGE_ID, PageSyncAction.CREATED)
