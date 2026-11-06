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
from sync_confluence.testspec._model import TestCase


def _labelled(parent: ElementType, label: str, text: str) -> None:
    paragraph = sub_element(parent, "p")
    sub_element(paragraph, "strong", f"{label}:").tail = f" {text}"


def _details(root: ElementType, case: TestCase) -> None:
    _labelled(root, "Vendor", case.vendor)
    _labelled(root, "Type", case.test_type)
    if case.tags:
        _labelled(root, "Tags", ", ".join(case.tags))
    sub_element(root, "h2", "Description")
    for paragraph in case.description.split("\n\n"):
        set_multiline(sub_element(root, "p"), paragraph.strip())


def render_test_case(
    case: TestCase, source_file: Path, generated_by: Optional[str] = None
) -> str:
    """Return the CSF body: details, description, inputs and outputs tables."""
    root = parse_document("")
    _details(root, case)
    sub_element(root, "h2", "Inputs")
    append_table(root, case.inputs)
    sub_element(root, "h2", "Outputs")
    append_table(root, case.outputs)
    prepend_generated_by_banner(root, generated_by, Path(source_file.name))
    return serialize_document(root)
