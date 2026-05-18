"""Top-level :func:`run` and :func:`main` entry points."""

from __future__ import annotations

import argparse
import logging
import sys

from sync_confluence.cli._args import parse_args, validate_args
from sync_confluence.cli._auth import _prepare_auth
from sync_confluence.cli._dispatch import _dispatch_sync
from sync_confluence.cli._docs import _resolve_docs
from sync_confluence.cli._finalise import _finalise_run
from sync_confluence.cli._plan import _resolve_sync_plan

log = logging.getLogger(__name__)


def _log_run_header(args: argparse.Namespace) -> None:
    log.info("Confluence: %s", args.url)
    log.info("Space: %s  |  Parent page: %s", args.space, args.parent_id)


def run(args: argparse.Namespace) -> int:
    """Execute the sync.  Returns an exit code (0 = success, 1 = error)."""
    _log_run_header(args)
    docs = _resolve_docs(args)
    if docs is None:
        return 1
    auth = _prepare_auth(args)
    if auth is None:
        return 1
    plan = _resolve_sync_plan(auth.confluence, args, auth.managed_by_label)
    sync_result = _dispatch_sync(args, docs, auth, plan)
    _finalise_run(sync_result, auth, plan, args)
    return 1 if sync_result.skipped else 0


def main() -> None:
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(levelname)s: %(message)s",
    )
    # Suppress the atlassian-python-api library's own INFO/DEBUG request logs
    # (e.g. "rest/api/content/{id}/child/page") — they add noise without value.
    logging.getLogger("atlassian").setLevel(logging.WARNING)
    validate_args(args)
    sys.exit(run(args))
