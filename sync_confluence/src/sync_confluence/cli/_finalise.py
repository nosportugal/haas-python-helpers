"""Orphan cleanup and end-of-run summary logging."""

from __future__ import annotations

import argparse
import logging

from sync_confluence.cli._auth import _AuthInfo
from sync_confluence.cli._plan import _SyncPlan
from sync_confluence.confluence import DeleteOrphansRequest, delete_orphans
from sync_confluence.traversal import SyncResult

log = logging.getLogger(__name__)

_DRY_RUN_ID = "DRY-RUN"


def _run_orphan_cleanup(
    auth: _AuthInfo, parent_id: str, sync_result: SyncResult, dry_run: bool
) -> int:
    if parent_id == _DRY_RUN_ID:
        log.info("[DRY-RUN] Skipping orphan check — parent page does not exist yet")
        return 0
    if not auth.managed_by_label:
        log.warning(
            "No managed-by label is set — orphan cleanup will target ALL "
            "unmatched pages under the parent regardless of origin."
        )
    request = DeleteOrphansRequest(
        root_page_id=parent_id,
        expected_titles=sync_result.expected_titles,
        dry_run=dry_run,
        managed_by_label=auth.managed_by_label,
        expected_paths=sync_result.expected_paths,
    )
    return delete_orphans(auth.confluence, request)


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


def _finalise_run(
    sync_result: SyncResult,
    auth: _AuthInfo,
    plan: _SyncPlan,
    args: argparse.Namespace,
) -> None:
    deleted = _run_orphan_cleanup(auth, plan.parent_id, sync_result, args.dry_run)
    _log_sync_summary(sync_result, deleted)
