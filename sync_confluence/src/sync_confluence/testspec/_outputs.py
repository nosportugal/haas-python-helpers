"""Validate and pretty-print the JSON cells of an Outputs sheet."""

from __future__ import annotations

import json

from sync_confluence.testspec._model import SheetTable, TestSpecError
from sync_confluence.testspec._sheets import column_index

CLI_COLUMN = "CLI"
JSON_COLUMN = "JSON"


def normalise_outputs(outputs: SheetTable, sheet_name: str) -> SheetTable:
    """Validate and pretty-print every JSON cell; require a JSON column."""
    json_col = column_index(outputs, JSON_COLUMN, sheet_name)
    for row_number, row in enumerate(outputs.rows, start=1):
        if not row[json_col].strip():
            continue
        try:
            document = json.loads(row[json_col])
        except json.JSONDecodeError as exc:
            raise TestSpecError(
                f"Sheet '{sheet_name}' data row {row_number}: invalid JSON ({exc})"
            ) from exc
        row[json_col] = json.dumps(document, indent=2, ensure_ascii=False)
    return outputs
