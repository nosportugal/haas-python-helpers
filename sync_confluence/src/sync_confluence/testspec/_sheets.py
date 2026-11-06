"""Read worksheets as header + rows of text cells."""

from __future__ import annotations

import datetime
from itertools import repeat
from typing import Any

from openpyxl.worksheet.worksheet import Worksheet

from sync_confluence.testspec._model import SheetTable, TestSpecError


def _datetime_text(cell_value: datetime.datetime) -> str:
    """Date-only cells come back as midnight datetimes; keep any real time."""
    if cell_value.time() == datetime.time.min:
        return cell_value.date().isoformat()
    return cell_value.isoformat(sep=" ")


def cell_text(cell_value: Any) -> str:
    """Render a cell value as the text a reader of the sheet would expect."""
    if cell_value is None:
        return ""
    if isinstance(cell_value, bool):
        return "true" if cell_value else "false"
    if isinstance(cell_value, float) and cell_value.is_integer():
        return str(int(cell_value))
    if isinstance(cell_value, datetime.datetime):
        return _datetime_text(cell_value)
    return str(cell_value).replace("\xa0", " ").rstrip()


def _fit(row: list[str], width: int) -> list[str]:
    fitted = row[:width]
    fitted.extend(repeat("", width - len(fitted)))
    return fitted


def read_sheet(worksheet: Worksheet) -> SheetTable:
    """Return the first non-empty row as headers and the non-empty rows below."""
    rows = [
        [cell_text(cell_value) for cell_value in row]
        for row in worksheet.iter_rows(values_only=True)
    ]
    rows = [row for row in rows if any(cell.strip() for cell in row)]
    if not rows:
        raise TestSpecError(f"Sheet '{worksheet.title}' is empty")
    headers = [header.strip() for header in rows[0]]
    while headers and not headers[-1]:
        headers.pop()
    return SheetTable(
        headers=headers,
        rows=[_fit(row, len(headers)) for row in rows[1:]],
    )


def column_index(table: SheetTable, header: str, sheet_name: str) -> int:
    """Return the position of *header* (case-insensitive) or raise."""
    wanted = header.casefold()
    for position, candidate in enumerate(table.headers):
        if candidate.casefold() == wanted:
            return position
    raise TestSpecError(f"Sheet '{sheet_name}' has no '{header}' column")
