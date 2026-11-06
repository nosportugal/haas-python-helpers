"""Read a test-specification workbook into :class:`TestCase` objects."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import openpyxl
from openpyxl.workbook.workbook import Workbook

from sync_confluence.testspec._index import read_index
from sync_confluence.testspec._join import join_inputs, normalise_outputs
from sync_confluence.testspec._model import SheetTable, TestCase, TestSpecError
from sync_confluence.testspec._sheets import read_sheet

PARAMETERS_SHEET = "Parameters"
INPUTS_SUFFIX = " - Inputs"
OUTPUTS_SUFFIX = " - Outputs"


def _optional_sheet(
    workbook: Workbook, sheets: dict[str, str], name: str
) -> Optional[SheetTable]:
    real_name = sheets.get(name.casefold())
    return None if real_name is None else read_sheet(workbook[real_name])


def _check_unexpected_sheets(sheets: dict[str, str], cases: list[TestCase]) -> None:
    index_key = next(iter(sheets))  # sheets keeps workbook order: first is the Index
    expected = {index_key, PARAMETERS_SHEET.casefold()}
    for case in cases:
        expected.add(f"{case.test_id}{INPUTS_SUFFIX}".casefold())
        expected.add(f"{case.test_id}{OUTPUTS_SUFFIX}".casefold())
    unexpected_keys = sheets.keys() - expected
    unexpected = ", ".join(sorted(sheets[key] for key in unexpected_keys))
    if unexpected:
        raise TestSpecError(f"Sheets not matching any Index ID: {unexpected}")


def _attach_sheets(
    case: TestCase,
    workbook: Workbook,
    sheets: dict[str, str],
    catalog: Optional[SheetTable],
) -> None:
    inputs_name = f"{case.test_id}{INPUTS_SUFFIX}"
    inputs = _optional_sheet(workbook, sheets, inputs_name)
    if inputs is not None:
        case.inputs = join_inputs(inputs, catalog, inputs_name)
    outputs_name = f"{case.test_id}{OUTPUTS_SUFFIX}"
    outputs = _optional_sheet(workbook, sheets, outputs_name)
    if outputs is not None:
        case.outputs = normalise_outputs(outputs, outputs_name)


def read_workbook(path: Path) -> list[TestCase]:
    """Parse and validate *path*; raise :class:`TestSpecError` on layout errors."""
    workbook = openpyxl.load_workbook(path, data_only=True)
    sheets = {name.strip().casefold(): name for name in workbook.sheetnames}
    cases = read_index(workbook, workbook.sheetnames[0])  # first sheet is the Index
    _check_unexpected_sheets(sheets, cases)
    catalog = _optional_sheet(workbook, sheets, PARAMETERS_SHEET)
    for case in cases:
        _attach_sheets(case, workbook, sheets, catalog)
    return cases
