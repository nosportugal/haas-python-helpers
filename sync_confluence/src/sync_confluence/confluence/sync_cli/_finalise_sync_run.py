"""Orphan cleanup and end-of-run summary logging."""

from __future__ import annotations

import logging

from sync_confluence.confluence import (
    DRY_RUN_PAGE_ID,
    DeleteOrphansRequest,
    delete_orphans,
)
from sync_confluence.confluence.sync_cli._confluence_session import ConfluenceSession
from sync_confluence.confluence.sync_cli._sync_result import SyncResult

log = logging.getLogger(__name__)


def _run_orphan_cleanup(
    session: ConfluenceSession,
    parent_id: str,
    sync_result: SyncResult,
    dry_run: bool,
) -> int:
    if parent_id == DRY_RUN_PAGE_ID:
        log.info("[DRY-RUN] Skipping orphan check — parent page does not exist yet")
        return 0
    if not session.managed_by_label:
        log.warning(
            "No managed-by label is set — orphan cleanup will target ALL "
            "unmatched pages under the parent regardless of origin."
        )
    request = DeleteOrphansRequest(
        root_page_id=parent_id,
        expected_titles=sync_result.expected_titles,
        dry_run=dry_run,
        managed_by_label=session.managed_by_label,
        expected_paths=sync_result.expected_paths,
    )
    return delete_orphans(session.confluence, request)


def _log_sync_summary(sync_result: SyncResult, deleted: int) -> None:
    log.info(
        "Sync complete — created: %d, updated: %d, unchanged: %d, "
        "skipped: %d, orphans deleted: %d",
        sync_result.stats["created"],
        sync_result.stats["updated"],
        sync_result.stats["unchanged"],
        sync_result.stats["skipped"],
        deleted,
    )
    if sync_result.skipped:
        log.warning(
            "%d page(s) skipped due to title collisions with unrelated "
            "Confluence pages — rename the source files to resolve: %s",
            len(sync_result.skipped),
            ", ".join(sync_result.skipped),
        )


def finalise_sync_run(
    sync_result: SyncResult,
    session: ConfluenceSession,
    parent_id: str,
    dry_run: bool,
) -> None:
    """Run orphan cleanup under *parent_id*, then log the sync run summary."""
    deleted = _run_orphan_cleanup(session, parent_id, sync_result, dry_run)
    _log_sync_summary(sync_result, deleted)
