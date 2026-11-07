"""Read and validate the Index sheet (the first sheet of the workbook)."""

from __future__ import annotations

import re

from openpyxl.workbook.workbook import Workbook

from sync_confluence.testspec._index_columns import IndexColumns, find_index_columns
from sync_confluence.testspec._model import TestCase, TestSpecError
from sync_confluence.testspec._sheets import read_sheet

_TEST_ID_RE = re.compile(r"^\d+(\.\d+)*$")
_TAG_SPLIT_RE = re.compile(r"[;,\n]")
_ID = "ID"
_NAME = "Name"
_DESCRIPTION = "Description"
_TAGS = "Tags"


def _check_test_id_is_text(workbook: Workbook, sheet_name: str, id_col: int) -> None:
    column = next(
        workbook[sheet_name].iter_cols(
            min_col=id_col + 1, max_col=id_col + 1, min_row=2, values_only=True
        ),
        (),
    )
    for cell_value in column:
        if isinstance(cell_value, (int, float)):
            raise TestSpecError(
                f"Sheet '{sheet_name}': ID {cell_value!r} is a number; "
                "format the ID column as Text so that 1.10 is not read as 1.1"
            )


def _tags(raw_tags: str) -> list[str]:
    return [tag.strip() for tag in _TAG_SPLIT_RE.split(raw_tags) if tag.strip()]


def _parse_index_row(row: list[str], columns: IndexColumns) -> TestCase:
    mandatory = columns.mandatory
    test_id = row[mandatory[_ID]].strip()
    if not _TEST_ID_RE.match(test_id):
        raise TestSpecError(
            f"Index: ID '{test_id}' must be dot-separated numbers, e.g. 1, 1.1 or 1.1.3"
        )
    name = row[mandatory[_NAME]].strip()
    if not name:
        raise TestSpecError(f"Index: test {test_id} needs a Name")
    return TestCase(
        test_id=test_id,
        name=name,
        description=row[mandatory[_DESCRIPTION]].strip(),
        tags=_tags(row[mandatory[_TAGS]]),
        extra_fields=[
            (header, row[position].strip()) for header, position in columns.extras
        ],
    )


def _check_unique_ids(cases: list[TestCase]) -> None:
    seen: set[str] = set()
    for case in cases:
        if case.test_id in seen:
            raise TestSpecError(f"Index: duplicate ID {case.test_id}")
        seen.add(case.test_id)


def read_index(workbook: Workbook, sheet_name: str) -> list[TestCase]:
    """Return one :class:`TestCase` (without inputs/outputs) per Index row."""
    index = read_sheet(workbook[sheet_name])
    columns = find_index_columns(index, sheet_name)
    _check_test_id_is_text(workbook, sheet_name, columns.mandatory[_ID])
    if not index.rows:
        # An empty sync would make orphan cleanup delete every published case.
        raise TestSpecError(f"Sheet '{sheet_name}' has no test cases")
    cases = [_parse_index_row(row, columns) for row in index.rows]
    _check_unique_ids(cases)
    return cases
