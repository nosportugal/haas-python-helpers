"""Join per-test Inputs with the Parameters catalog and validate Outputs JSON."""

from __future__ import annotations

import json
from itertools import repeat
from typing import Optional

from sync_confluence.testspec._model import SheetTable, TestSpecError
from sync_confluence.testspec._sheets import column_index

PARAMETER_COLUMN = "Parameter"
VALUE_COLUMN = "Value"
CLI_COLUMN = "CLI"
JSON_COLUMN = "JSON"


def _without(row: list[str], position: int) -> list[str]:
    return row[:position] + row[position + 1 :]


def _inputs_by_parameter(inputs: SheetTable, sheet_name: str) -> dict[str, list[str]]:
    param_col = column_index(inputs, PARAMETER_COLUMN, sheet_name)
    column_index(inputs, VALUE_COLUMN, sheet_name)
    by_name: dict[str, list[str]] = {}
    for row_number, row in enumerate(inputs.rows, start=1):
        name = row[param_col].strip()
        if not name:
            raise TestSpecError(
                f"Sheet '{sheet_name}' data row {row_number}: blank Parameter name"
            )
        if name in by_name:
            raise TestSpecError(f"Sheet '{sheet_name}': duplicate parameter '{name}'")
        by_name[name] = _without(row, param_col)
    return by_name


def _check_known(by_name: dict, catalog_names: set[str], sheet_name: str) -> None:
    unknown = sorted(set(by_name) - catalog_names)
    if unknown:
        unknown_text = ", ".join(unknown)
        raise TestSpecError(
            f"Sheet '{sheet_name}': parameters not in the Parameters sheet: "
            f"{unknown_text}"
        )


def join_inputs(
    inputs: SheetTable, catalog: Optional[SheetTable], sheet_name: str
) -> SheetTable:
    """Return every catalog parameter with this test's value columns appended."""
    by_name = _inputs_by_parameter(inputs, sheet_name)
    if catalog is None:
        return inputs
    catalog_col = column_index(catalog, PARAMETER_COLUMN, "Parameters")
    _check_known(
        by_name, {row[catalog_col].strip() for row in catalog.rows}, sheet_name
    )
    extra_headers = _without(
        inputs.headers, column_index(inputs, PARAMETER_COLUMN, sheet_name)
    )
    blanks = list(repeat("", len(extra_headers)))
    return SheetTable(
        headers=catalog.headers + extra_headers,
        rows=[
            row + by_name.get(row[catalog_col].strip(), blanks) for row in catalog.rows
        ],
    )


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
