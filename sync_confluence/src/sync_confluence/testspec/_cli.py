"""Command-line entry point for ``sync-confluence-testspec``."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from sync_confluence.cli._auth import _AuthInfo, _prepare_auth
from sync_confluence.cli._finalise import _finalise_run
from sync_confluence.cli._plan import _SyncPlan
from sync_confluence.testspec._args import missing_required, parse_args
from sync_confluence.testspec._model import TestSpecError, TestSpecSyncConfig
from sync_confluence.testspec._reader import read_workbook
from sync_confluence.testspec._sync import sync_test_cases

log = logging.getLogger(__name__)


def _sync_config(args: argparse.Namespace, auth: _AuthInfo) -> TestSpecSyncConfig:
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


def run(args: argparse.Namespace) -> int:
    """Read, validate and sync the workbook.  Returns the process exit code."""
    try:
        cases = read_workbook(Path(args.xlsx))
    except (OSError, TestSpecError) as exc:
        log.error("Cannot read %s: %s", args.xlsx, exc)
        return 1
    log.info("Read %d test case(s) from %s", len(cases), args.xlsx)
    auth = _prepare_auth(args)
    if auth is None:
        return 1
    sync_result = sync_test_cases(auth.confluence, cases, _sync_config(args, auth))
    plan = _SyncPlan(parent_id=args.parent_id, readme_as_parent=False, depth=0)
    _finalise_run(sync_result, auth, plan, args)
    return 1 if sync_result.skipped else 0


def main() -> None:
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(levelname)s: %(message)s",
    )
    logging.getLogger("atlassian").setLevel(logging.WARNING)
    missing = missing_required(args)
    if missing:
        log.error("Missing required configuration: %s", ", ".join(missing))
        sys.exit(2)
    sys.exit(run(args))
