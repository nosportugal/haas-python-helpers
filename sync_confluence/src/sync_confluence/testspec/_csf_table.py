"""Build CSF paragraphs and tables from sheet text."""

from __future__ import annotations

from typing import Optional

from lxml import etree

from sync_confluence.confluence.storage_format import ElementType
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


def append_table(parent: ElementType, table: Optional[SheetTable]) -> None:
    """Append *table* exactly as laid out in the sheet, or a placeholder."""
    if table is None or not table.rows:
        sub_element(sub_element(parent, "p"), "em", _NOT_SPECIFIED)
        return
    body = sub_element(sub_element(parent, "table"), "tbody")
    _append_row(body, "th", table.headers)
    for row in table.rows:
        _append_row(body, "td", row)
