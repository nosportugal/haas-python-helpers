"""Command-line entry point for ``sync-confluence-testspec``."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from sync_confluence.confluence.sync_cli import (
    ConfluenceSession,
    finalise_sync_run,
    open_confluence_session,
)
from sync_confluence.testspec._args import (
    missing_required,
    parse_testspec_sync_args,
)
from sync_confluence.testspec._model import TestSpecError, TestSpecSyncConfig
from sync_confluence.testspec._reader import read_workbook
from sync_confluence.testspec._sync import sync_test_cases

log = logging.getLogger(__name__)


def _sync_config(
    args: argparse.Namespace, auth: ConfluenceSession
) -> TestSpecSyncConfig:
    return TestSpecSyncConfig(
        space_key=args.space,
        parent_id=args.parent_id,
        source_file=Path(Path(args.xlsx).name),
        dry_run=args.dry_run,
        managed_by_label=auth.managed_by_label,
        restrict_edits_to=auth.restrict_edits_to,
        page_width=args.page_width,
        generated_by="" if args.no_generated_by else args.generated_by,
    )


def run_testspec_sync(args: argparse.Namespace) -> int:
    """Read, validate and sync the workbook.  Returns the process exit code."""
    try:
        cases = read_workbook(Path(args.xlsx))
    except (OSError, TestSpecError) as exc:
        log.error("Cannot read %s: %s", args.xlsx, exc)
        return 1
    log.info("Read %d test case(s) from %s", len(cases), args.xlsx)
    auth = open_confluence_session(args)
    if auth is None:
        return 1
    sync_result = sync_test_cases(auth.confluence, cases, _sync_config(args, auth))
    finalise_sync_run(sync_result, auth, args.parent_id, args.dry_run)
    return 1 if sync_result.skipped else 0


def testspec_sync_main() -> None:
    """Run the ``sync-confluence-testspec`` command-line entry point."""
    args = parse_testspec_sync_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(levelname)s: %(message)s",
    )
    logging.getLogger("atlassian").setLevel(logging.WARNING)
    missing = missing_required(args)
    if missing:
        log.error("Missing required configuration: %s", ", ".join(missing))
        sys.exit(2)
    sys.exit(run_testspec_sync(args))
