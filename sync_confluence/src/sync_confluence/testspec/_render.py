"""Render a :class:`TestCase` as a Confluence Storage Format page body."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from sync_confluence.confluence.storage_format import (
    ElementType,
    parse_document,
    prepend_generated_by_banner,
    serialize_document,
)
from sync_confluence.testspec._csf_table import (
    append_table,
    set_multiline,
    sub_element,
)
from sync_confluence.testspec._json_cells import JsonCells
from sync_confluence.testspec._model import TestCase

_EMPTY_VALUE = "-"


def _labelled(parent: ElementType, label: str, text: str) -> None:
    paragraph = sub_element(parent, "p")
    lines = (text or _EMPTY_VALUE).split("\n")
    sub_element(paragraph, "strong", f"{label}:").tail = f" {lines[0]}"
    for line in lines[1:]:
        sub_element(paragraph, "br").tail = line


def _details(root: ElementType, case: TestCase) -> None:
    """Tags first, then the additional Index columns in table order."""
    _labelled(root, "Tags", ", ".join(case.tags))
    for label, field_text in case.extra_fields:
        _labelled(root, label, field_text)
    sub_element(root, "h2", "Description")
    for paragraph in case.description.split("\n\n"):
        set_multiline(sub_element(root, "p"), paragraph.strip())


def render_test_case(
    case: TestCase,
    source_file: Path,
    generated_by: Optional[str] = None,
    reformat_json: bool = False,
) -> str:
    """Return the CSF body: details, description, inputs and outputs tables.

    With *reformat_json*, valid JSON under a ``JSON`` header is pretty-printed.
    """
    root = parse_document("")
    _details(root, case)
    for heading, table in (("Inputs", case.inputs), ("Outputs", case.outputs)):
        sub_element(root, "h2", heading)
        label = f"Sheet '{case.test_id} - {heading}'"
        append_table(root, table, JsonCells(reformat_json, label))
    prepend_generated_by_banner(root, generated_by, Path(source_file.name))
    return serialize_document(root)
