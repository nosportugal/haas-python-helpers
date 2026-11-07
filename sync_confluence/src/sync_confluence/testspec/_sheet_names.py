"""Names of the per-test sheets and the error explaining a stray sheet."""

from __future__ import annotations

import re
from typing import Iterable

INPUTS_SUFFIX = " - Inputs"
OUTPUTS_SUFFIX = " - Outputs"

# Loose on purpose: it recognises near misses such as "1.1- Inputs".
_NEAR_MISS_RE = re.compile(r"^(?P<test_id>.*?)\s*-\s*(?P<kind>inputs|outputs)$", re.I)


def expected_sheet_names(test_ids: Iterable[str]) -> set[str]:
    """Return the casefolded per-test sheet names for *test_ids*."""
    return {
        f"{test_id}{suffix}".casefold()
        for test_id in test_ids
        for suffix in (INPUTS_SUFFIX, OUTPUTS_SUFFIX)
    }


def _explain(sheet_name: str, test_ids: set[str]) -> str:
    near_miss = _NEAR_MISS_RE.match(sheet_name.strip())
    if near_miss is None:
        return (
            f"'{sheet_name}' is neither the Index (first sheet) nor named "
            "'<ID> - Inputs' or '<ID> - Outputs'"
        )
    test_id = near_miss["test_id"]
    if test_id in test_ids:
        kind = near_miss["kind"].capitalize()
        return f"'{sheet_name}' must be named exactly '{test_id} - {kind}'"
    return f"'{sheet_name}' refers to ID '{test_id}', which is not in the Index"


def unexpected_sheets_message(sheet_names: list[str], test_ids: list[str]) -> str:
    """Explain, per sheet, why it is not allowed in the workbook."""
    known_ids = set(test_ids)
    reasons = "; ".join(_explain(name, known_ids) for name in sheet_names)
    id_list = ", ".join(test_ids)
    return (
        f"Unexpected sheet(s): {reasons}. Besides the Index (first sheet), only "
        "'<ID> - Inputs' and '<ID> - Outputs' sheets are allowed, where <ID> is "
        f"listed in the Index (IDs: {id_list})"
    )
