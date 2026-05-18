"""Confluence connection, account-id resolution and managed-by label setup."""

from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass
from typing import Optional

from atlassian import Confluence

from sync_confluence.cli._env import _detect_repo_url
from sync_confluence.cli._resolve import _resolve_managed_by_label

log = logging.getLogger(__name__)

_DRY_RUN_ID = "DRY-RUN"


@dataclass
class _AuthInfo:
    """Confluence connection plus repository/label metadata."""

    confluence: Confluence
    repo_url: Optional[str]
    managed_by_label: Optional[str]
    restrict_edits_to: str


def _connect_confluence(args: argparse.Namespace) -> Confluence:
    return Confluence(
        url=args.url, username=args.email, password=args.token, cloud=True
    )


def _resolve_restrict_edits_to(
    confluence: Confluence, args: argparse.Namespace
) -> Optional[str]:
    """Return the accountId to restrict edits to (``"DRY-RUN"`` in dry-run)."""
    user_details = confluence.get("rest/api/user/current")
    if not user_details or "accountId" not in user_details:
        log.error(
            "Could not resolve accountId for '%s'. "
            "Edit restrictions cannot be applied.",
            args.email,
        )
        return None
    if args.dry_run:
        log.info("[DRY-RUN] Would apply edit restrictions (authenticated user)")
        return _DRY_RUN_ID
    account_id = user_details["accountId"]
    log.info("Edit restrictions enabled for accountId=%s", account_id)
    return account_id


def _prepare_auth(args: argparse.Namespace) -> Optional[_AuthInfo]:
    """Detect repo URL, derive label, connect, resolve account id."""
    repo_url = _detect_repo_url()
    if not repo_url:
        log.warning(
            "Could not detect repository URL: not inside a git repository "
            "and GITHUB_SERVER_URL / GITHUB_REPOSITORY are not set. "
            "Relative links will not be rewritten and managed-by label "
            "cannot be auto-derived."
        )
    managed_by_label = _resolve_managed_by_label(args, repo_url)
    confluence = _connect_confluence(args)
    restrict_edits_to = _resolve_restrict_edits_to(confluence, args)
    if restrict_edits_to is None:
        return None
    return _AuthInfo(
        confluence=confluence,
        repo_url=repo_url,
        managed_by_label=managed_by_label,
        restrict_edits_to=restrict_edits_to,
    )
