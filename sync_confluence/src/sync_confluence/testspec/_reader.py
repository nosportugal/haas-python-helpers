"""Read a test-specification workbook into :class:`TestCase` objects."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import openpyxl
from openpyxl.workbook.workbook import Workbook

from sync_confluence.testspec._index import read_index
from sync_confluence.testspec._model import SheetTable, TestCase, TestSpecError
from sync_confluence.testspec._sheet_names import (
    INPUTS_SUFFIX,
    OUTPUTS_SUFFIX,
    expected_sheet_names,
    unexpected_sheets_message,
)
from sync_confluence.testspec._sheets import read_sheet


def _optional_sheet(
    workbook: Workbook, sheets: dict[str, str], name: str
) -> Optional[SheetTable]:
    real_name = sheets.get(name.casefold())
    return None if real_name is None else read_sheet(workbook[real_name])


def _stray_sheets(sheets: dict[str, str], test_ids: list[str]) -> list[str]:
    index_key = next(iter(sheets))  # sheets keeps workbook order: first is the Index
    expected = {index_key, *expected_sheet_names(test_ids)}
    return [name for key, name in sheets.items() if key not in expected]


def _check_unexpected_sheets(sheets: dict[str, str], cases: list[TestCase]) -> None:
    test_ids = [case.test_id for case in cases]
    stray = _stray_sheets(sheets, test_ids)
    if stray:
        raise TestSpecError(unexpected_sheets_message(stray, test_ids))


def _attach_sheets(case: TestCase, workbook: Workbook, sheets: dict[str, str]) -> None:
    case.inputs = _optional_sheet(workbook, sheets, f"{case.test_id}{INPUTS_SUFFIX}")
    case.outputs = _optional_sheet(workbook, sheets, f"{case.test_id}{OUTPUTS_SUFFIX}")


def read_workbook(path: Path) -> list[TestCase]:
    """Parse and validate *path*; raise :class:`TestSpecError` on layout errors."""
    workbook = openpyxl.load_workbook(path, data_only=True)
    sheets = {name.strip().casefold(): name for name in workbook.sheetnames}
    cases = read_index(workbook, workbook.sheetnames[0])  # first sheet is the Index
    _check_unexpected_sheets(sheets, cases)
    for case in cases:
        _attach_sheets(case, workbook, sheets)
    return cases
