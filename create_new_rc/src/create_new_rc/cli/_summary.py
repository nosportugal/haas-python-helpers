"""Print the workflow summary (phase 7)."""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)

_SUMMARY_WIDTH = 50


def print_summary(
    repo: str,
    next_tag: str,
    release_branch: str,
    existed: bool,
    dry_run: bool,
) -> None:
    """Print a summary of what was done (or would be done in dry-run mode)."""
    prefix = "[DRY RUN] " if dry_run else ""
    branch_status = "already existed" if existed else "created"
    log.info("=" * _SUMMARY_WIDTH)
    log.info("%sSummary", prefix)
    log.info("=" * _SUMMARY_WIDTH)
    log.info("  Repository : %s", repo)
    log.info("  Tag        : %s", next_tag)
    log.info("  Branch     : %s  (%s)", release_branch, branch_status)
