"""Build CSF paragraphs and tables from sheet text."""

from __future__ import annotations

from types import MappingProxyType
from typing import Optional

from lxml import etree

from sync_confluence.confluence.storage_format import ElementType, build_code_macro
from sync_confluence.testspec._model import SheetTable
from sync_confluence.testspec._outputs import CLI_COLUMN, JSON_COLUMN

_NOT_SPECIFIED = "Not specified yet."
_CODE_LANGUAGES = MappingProxyType(
    {CLI_COLUMN.casefold(): None, JSON_COLUMN.casefold(): "json"}
)


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


def _cell(row: ElementType, header: str, text: str) -> None:
    cell = sub_element(row, "td")
    language_key = header.casefold()
    if language_key in _CODE_LANGUAGES and text.strip():
        language = _CODE_LANGUAGES[language_key]
        cell.append(build_code_macro(text, language))
        return
    set_multiline(cell, text)


def _header_row(body: ElementType, headers: list[str]) -> None:
    row = sub_element(body, "tr")
    for header in headers:
        sub_element(row, "th", header)


def append_table(parent: ElementType, table: Optional[SheetTable]) -> None:
    """Append *table* (CLI/JSON cells as code macros) or a placeholder."""
    if table is None or not table.rows:
        sub_element(sub_element(parent, "p"), "em", _NOT_SPECIFIED)
        return
    body = sub_element(sub_element(parent, "table"), "tbody")
    _header_row(body, table.headers)
    for row in table.rows:
        data_row = sub_element(body, "tr")
        for header, text in zip(table.headers, row):
            _cell(data_row, header, text)
