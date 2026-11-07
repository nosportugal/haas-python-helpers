"""Build CSF paragraphs and tables from sheet text."""

from __future__ import annotations

from typing import Optional

from lxml import etree

from sync_confluence.confluence.storage_format import ElementType
from sync_confluence.testspec._json_cells import (
    JsonCells,
    append_json_cell,
    is_json_header,
)
from sync_confluence.testspec._model import SheetTable

_NOT_SPECIFIED = "Not specified yet."


def sub_element(parent: ElementType, tag: str, text: str = "") -> ElementType:
    """Append a ``<tag>`` child with optional *text* to *parent*."""
    element = etree.SubElement(parent, tag)
    if text:
        element.text = text
    return element


def set_multiline(parent: ElementType, text: str) -> None:
    """Set *text* on *parent*, turning newlines into ``<br/>``."""
    lines = text.split("\n")
    parent.text = lines[0]
    for line in lines[1:]:
        sub_element(parent, "br").tail = line


def _append_row(body: ElementType, tag: str, cells: list[str]) -> None:
    row = sub_element(body, "tr")
    for cell_text in cells:
        set_multiline(sub_element(row, tag), cell_text)


def _append_data_row(
    body: ElementType,
    cells: list[str],
    json_columns: set[int],
    json_cells: JsonCells,
) -> None:
    row = sub_element(body, "tr")
    for position, cell_text in enumerate(cells):
        cell = sub_element(row, "td")
        if position in json_columns and cell_text.strip():
            append_json_cell(cell, cell_text, json_cells)
        else:
            set_multiline(cell, cell_text)


def _json_columns(headers: list[str]) -> set[int]:
    return {pos for pos, header in enumerate(headers) if is_json_header(header)}


def append_table(
    parent: ElementType,
    table: Optional[SheetTable],
    json_cells: Optional[JsonCells] = None,
) -> None:
    """Append *table* as laid out in the sheet, or a placeholder.

    Cells under a ``JSON`` header become JSON code blocks; everything else is
    plain text with line breaks kept.
    """
    if table is None or not table.rows:
        sub_element(sub_element(parent, "p"), "em", _NOT_SPECIFIED)
        return
    options = json_cells or JsonCells()
    body = sub_element(sub_element(parent, "table"), "tbody")
    _append_row(body, "th", table.headers)
    for row_number, row in enumerate(table.rows, start=1):
        row_options = options._replace(label=f"{options.label} data row {row_number}")
        _append_data_row(body, row, _json_columns(table.headers), row_options)
