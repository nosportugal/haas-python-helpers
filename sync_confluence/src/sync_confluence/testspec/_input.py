"""Read and validate everything a sync needs from the command line."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import NamedTuple, Optional

from sync_confluence.testspec._args import resolve_suite
from sync_confluence.testspec._model import TestCase, TestSpecError
from sync_confluence.testspec._reader import read_workbook
from sync_confluence.testspec._titles import check_title_lengths

log = logging.getLogger(__name__)


class WorkbookInput(NamedTuple):
    """The suite ID and the test cases of one workbook."""

    suite: str
    cases: list[TestCase]


def _load_input(args: argparse.Namespace) -> WorkbookInput:
    suite = resolve_suite(args)
    cases = read_workbook(Path(args.xlsx))
    check_title_lengths(cases, suite)
    return WorkbookInput(suite, cases)


def read_input(args: argparse.Namespace) -> Optional[WorkbookInput]:
    """Return the suite and test cases, or ``None`` after logging why not."""
    try:
        workbook_input = _load_input(args)
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
