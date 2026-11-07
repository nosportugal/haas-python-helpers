"""Cells under a ``JSON`` header: shown as JSON, never rejected."""

from __future__ import annotations

import json
import logging
from typing import NamedTuple

from sync_confluence.confluence.storage_format import ElementType, build_code_macro

log = logging.getLogger(__name__)

_JSON_HEADER = "json"


def is_json_header(header: str) -> bool:
    """True for a ``JSON`` column header (case and outer spaces ignored)."""
    return header.strip().casefold() == _JSON_HEADER


def json_cell_text(cell_text: str, reformat: bool, where: str) -> str:
    """Return the text to show for one ``JSON`` cell.

    The text is kept as written unless *reformat* is set and it parses as
    JSON, in which case it is pretty-printed.  A cell that does not parse
    (a fragment, a placeholder, several documents) is shown unchanged and
    logged as a warning: the authors of the workbook decide what it holds.
    """
    try:
        document = json.loads(cell_text)
    except ValueError as exc:  # JSONDecodeError, oversized integer strings
        log.warning("%s: not valid JSON (%s); shown unchanged", where, exc)
        return cell_text
    if reformat:
        try:
            return json.dumps(
                document, indent=2, ensure_ascii=False, allow_nan=False
            )
        except ValueError as exc:  # non-finite floats such as 1e400
            log.warning("%s: cannot be reformatted (%s); shown unchanged", where, exc)
    return cell_text


class JsonCells(NamedTuple):
    """How cells under a ``JSON`` header are shown, and how to name them."""

    reformat: bool = False
    label: str = ""


def append_json_cell(cell: ElementType, cell_text: str, json_cells: JsonCells) -> None:
    """Fill *cell* with *cell_text* as a JSON code block."""
    shown = json_cell_text(cell_text, json_cells.reformat, json_cells.label)
    cell.append(build_code_macro(shown, "json"))
