"""Command-line entry point for ``sync-confluence-testspec``."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import NamedTuple, Optional

from sync_confluence.confluence import FolderConflictError
from sync_confluence.confluence.sync_cli import (
    ConfluenceSession,
    finalise_sync_run,
    open_confluence_session,
)
from sync_confluence.testspec._args import (
    missing_required,
    parse_testspec_sync_args,
    resolve_suite,
)
from sync_confluence.testspec._model import (
    TestCase,
    TestSpecError,
    TestSpecSyncConfig,
    suite_source_prefix,
)
from sync_confluence.testspec._reader import read_workbook
from sync_confluence.testspec._sync import sync_test_cases

log = logging.getLogger(__name__)

# Testspec pages get their own default managed-by label so that Markdown sync
# and testspec sync under the same parent never treat each other's pages as
# orphans.
_LABEL_SUFFIX = "-testspec"


def _sync_config(
    args: argparse.Namespace, auth: ConfluenceSession, suite: str
) -> TestSpecSyncConfig:
    return TestSpecSyncConfig(
        space_key=args.space,
        parent_id=args.parent_id,
        source_file=Path(Path(args.xlsx).name),
        suite=suite,
        dry_run=args.dry_run,
        managed_by_label=auth.managed_by_label,
        restrict_edits_to=auth.restrict_edits_to,
        page_width=args.page_width,
        generated_by="" if args.no_generated_by else args.generated_by,
        reformat_json=args.format_json,
    )


class _WorkbookInput(NamedTuple):
    suite: str
    cases: list[TestCase]


def _read_input(args: argparse.Namespace) -> Optional[_WorkbookInput]:
    """Return the suite and test cases, or ``None`` after logging why not."""
    try:
        workbook_input = _WorkbookInput(
            resolve_suite(args), read_workbook(Path(args.xlsx))
        )
    except (OSError, TestSpecError) as exc:
        log.error("Cannot read %s: %s", args.xlsx, exc)
        return None
    log.info(
        "Read %d test case(s) of suite '%s' from %s",
        len(workbook_input.cases),
        workbook_input.suite,
        args.xlsx,
    )
    return workbook_input


def run_testspec_sync(args: argparse.Namespace) -> int:
    """Read, validate and sync the workbook.  Returns the process exit code."""
    workbook_input = _read_input(args)
    if workbook_input is None:
        return 1
    suite, cases = workbook_input
    auth = open_confluence_session(args, label_suffix=_LABEL_SUFFIX)
    if auth is None:
        return 1
    try:
        sync_result = sync_test_cases(
            auth.confluence, cases, _sync_config(args, auth, suite)
        )
    except FolderConflictError as exc:
        log.error("%s Orphan cleanup was not run.", exc)
        return 1
    finalise_sync_run(
        sync_result,
        auth,
        args.parent_id,
        args.dry_run,
        source_path_prefix=suite_source_prefix(suite),
    )
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
