"""Locate the mandatory and additional columns of the Index sheet."""

from __future__ import annotations

from typing import NamedTuple

from sync_confluence.testspec._model import SheetTable, TestSpecError
from sync_confluence.testspec._sheets import column_index

MANDATORY_COLUMNS = ("ID", "Name", "Description", "Tags")


class IndexColumns(NamedTuple):
    """Column positions: the mandatory ones by header, extras in table order."""

    mandatory: dict[str, int]
    extras: list[tuple[str, int]]


def _check_headers(table: SheetTable, sheet_name: str) -> None:
    seen: set[str] = set()
    for position, header in enumerate(table.headers, start=1):
        key = header.casefold()
        if not key:
            raise TestSpecError(
                f"Sheet '{sheet_name}': column {position} has no header"
            )
        if key in seen:
            raise TestSpecError(f"Sheet '{sheet_name}': duplicate column '{header}'")
        seen.add(key)


def find_index_columns(table: SheetTable, sheet_name: str) -> IndexColumns:
    """Return the mandatory column positions and the additional columns.

    Every header that is not mandatory is an additional column; it keeps its
    position in the table.  Raises :class:`TestSpecError` when a mandatory
    column is missing or a header is blank or repeated.
    """
    _check_headers(table, sheet_name)
    mandatory = {
        header: column_index(table, header, sheet_name) for header in MANDATORY_COLUMNS
    }
    taken = set(mandatory.values())
    extras = [
        (header, position)
        for position, header in enumerate(table.headers)
        if position not in taken
    ]
    return IndexColumns(mandatory, extras)
