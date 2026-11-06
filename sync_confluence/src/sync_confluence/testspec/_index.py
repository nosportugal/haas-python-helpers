"""Read and validate the Index sheet."""

from __future__ import annotations

import re

from openpyxl.workbook.workbook import Workbook

from sync_confluence.testspec._model import TestCase, TestSpecError
from sync_confluence.testspec._sheets import column_index, read_sheet

INDEX_SHEET = "Index"
TEST_TYPES = ("Create", "Modify", "Delete")

_TEST_TYPES_TEXT = ", ".join(TEST_TYPES)
_TEST_ID_RE = re.compile(r"^\d+\.\d+$")
_TAG_SPLIT_RE = re.compile(r"[;,\n]")
_TEST_ID = "Test ID"
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
                f"Sheet '{sheet_name}': Test ID {cell_value!r} is a number; "
                "format the Test ID column as Text so that 1.10 is not read as 1.1"
            )


def _tags(row: list[str], cols: dict[str, int]) -> list[str]:
    tags_col = cols.get(_TAGS)
    raw_tags = "" if tags_col is None else row[tags_col]
    return [tag.strip() for tag in _TAG_SPLIT_RE.split(raw_tags) if tag.strip()]


def _parse_index_row(row: list[str], cols: dict[str, int]) -> TestCase:
    test_id = row[cols[_TEST_ID]].strip()
    if not _TEST_ID_RE.match(test_id):
        raise TestSpecError(f"Index: Test ID '{test_id}' is not in the n.n format")
    test_type = row[cols["Type"]].strip().capitalize()
    if test_type not in TEST_TYPES:
        raise TestSpecError(
            f"Index: test {test_id} has Type '{test_type}'; "
            f"expected one of {_TEST_TYPES_TEXT}"
        )
    name = row[cols["Name"]].strip()
    vendor = row[cols["Vendor"]].strip()
    if not name or not vendor:
        raise TestSpecError(f"Index: test {test_id} needs a Name and a Vendor")
    return TestCase(
        test_id=test_id,
        name=name,
        description=row[cols["Description"]].strip(),
        test_type=test_type,
        vendor=vendor,
        tags=_tags(row, cols),
    )


def _check_unique_ids(cases: list[TestCase]) -> None:
    seen: set[str] = set()
    for case in cases:
        if case.test_id in seen:
            raise TestSpecError(f"Index: duplicate Test ID {case.test_id}")
        seen.add(case.test_id)


def read_index(workbook: Workbook, sheet_name: str) -> list[TestCase]:
    """Return one :class:`TestCase` (without inputs/outputs) per Index row."""
    index = read_sheet(workbook[sheet_name])
    cols = {
        header: column_index(index, header, sheet_name)
        for header in (_TEST_ID, "Name", "Description", "Type", "Vendor")
    }
    if _TAGS.casefold() in (header.casefold() for header in index.headers):
        cols[_TAGS] = column_index(index, _TAGS, sheet_name)
    _check_test_id_is_text(workbook, sheet_name, cols[_TEST_ID])
    if not index.rows:
        # An empty sync would make orphan cleanup delete every published case.
        raise TestSpecError(f"Sheet '{sheet_name}' has no test cases")
    cases = [_parse_index_row(row, cols) for row in index.rows]
    _check_unique_ids(cases)
    return cases
