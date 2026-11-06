"""Sync a test-specification workbook (.xlsx) to Confluence Cloud.

Public surface:

- :func:`read_workbook` — parse and validate a workbook into :class:`TestCase` objects.
- :func:`render_test_case` — render one test case as a CSF page body.
- :func:`sync_test_cases` — publish test cases (one folder per suite).
- :func:`testspec_sync_main` — ``sync-confluence-testspec`` entry point.
- :func:`run_testspec_sync`, :func:`parse_testspec_sync_args` — run / parse args.
"""

from sync_confluence.testspec._args import parse_testspec_sync_args
from sync_confluence.testspec._cli import run_testspec_sync, testspec_sync_main
from sync_confluence.testspec._labels import page_labels
from sync_confluence.testspec._model import (
    SheetTable,
    TestCase,
    TestSpecError,
    TestSpecSyncConfig,
)
from sync_confluence.testspec._reader import read_workbook
from sync_confluence.testspec._render import render_test_case
from sync_confluence.testspec._sync import sync_test_cases

__all__ = [
    "SheetTable",
    "TestCase",
    "TestSpecError",
    "TestSpecSyncConfig",
    "page_labels",
    "parse_testspec_sync_args",
    "read_workbook",
    "render_test_case",
    "run_testspec_sync",
    "sync_test_cases",
    "testspec_sync_main",
]
