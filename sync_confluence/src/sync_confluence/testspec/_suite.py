"""The suite ID: read from the workbook file name, ``<ID>[__<description>].xlsx``.

The suite ID is what keeps the pages of different workbooks apart in a
Confluence space, so it has a fixed shape that is checked before any
Confluence call:

- ``ID`` is a Jira-style project key followed by one to three segments
  (``HAAS-493``, ``HAAS-L3VPN-CISCO``, ``HAAS-ROUTING_CORE-E2E``): uppercase
  ASCII letters and digits only, ``-`` between parts, ``_`` joining words
  inside a segment, at most 24 characters.
- ``__`` (two underscores) ends the ID.  What follows is a free description
  that never affects identity, so renaming or versioning a file is safe.
"""

from __future__ import annotations

import re
from pathlib import Path

from sync_confluence.testspec._model import TestSpecError

SUITE_ID_MAX_LENGTH = 24

_SEPARATOR = "__"
_ID_PATTERN = r"[A-Z][A-Z0-9]{1,9}(?:-[A-Z0-9]+(?:_[A-Z0-9]+)*){1,3}"
_ID_RE = re.compile(rf"^{_ID_PATTERN}$")
# A valid ID, one "_", then more text: probably a description missing its "__".
_DESCRIPTION_SPLIT_RE = re.compile(rf"^(?P<head>{_ID_PATTERN})_(?P<tail>[^_].*)$")
_DESCRIPTION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_INVALID_CHAR_RE = re.compile(r"[^A-Za-z0-9._-]")
_SINGLE_UNDERSCORE_HINT = (
    " Did you mean '{head}__{tail}'? A single '_' only joins words inside the "
    "ID; '__' ends it."
)
_EXPECTED_ID = (
    "Expected <PROJECT>-<SEGMENT>[-<SEGMENT>...] with 1 to 3 segments, "
    "uppercase ASCII letters and digits only, '_' joining words inside a "
    "segment, and a project of 2 to 10 characters starting with a letter "
    "(e.g. HAAS-L3VPN-CISCO)."
)


def _check_characters(stem: str) -> None:
    if any(char.isspace() for char in stem):
        raise TestSpecError(
            f"The workbook file name {stem!r} must not contain spaces: use '_' "
            "between words"
        )
    invalid = sorted(set(_INVALID_CHAR_RE.findall(stem)))
    if invalid:
        found = " ".join(map(repr, invalid))
        raise TestSpecError(
            f"The workbook file name {stem!r} may only contain ASCII letters, "
            f"digits and '.', '_', '-'; found {found}"
        )


def _check_description(description: str) -> None:
    if not _DESCRIPTION_RE.match(description):
        raise TestSpecError(
            f"The description after '{_SEPARATOR}' ({description!r}) must start "
            "with a letter or digit"
        )


def _single_underscore_hint(id_part: str) -> str:
    """Suggest ``__`` when a single ``_`` seems to start a description."""
    split = _DESCRIPTION_SPLIT_RE.match(id_part)
    if split is None:
        return ""
    return _SINGLE_UNDERSCORE_HINT.format(**split.groupdict())


def _bad_id_message(id_part: str) -> str:
    uppercase = "" if id_part == id_part.upper() else " The ID must be uppercase."
    return (
        f"Invalid suite ID {id_part!r}. {_EXPECTED_ID}{uppercase}"
        f"{_single_underscore_hint(id_part)}"
    )


def validate_suite_id(suite: str) -> str:
    """Return *suite* if it is a valid suite ID, else raise with the reason."""
    if not _ID_RE.match(suite):
        raise TestSpecError(_bad_id_message(suite))
    if len(suite) > SUITE_ID_MAX_LENGTH:
        raise TestSpecError(
            f"Suite ID {suite!r} has {len(suite)} characters; at most "
            f"{SUITE_ID_MAX_LENGTH} are allowed"
        )
    return suite


def suite_from_filename(file_name: str) -> str:
    """Return the suite ID from ``<ID>[__<description>].xlsx``."""
    stem = Path(file_name).stem
    _check_characters(stem)
    id_part, separator, description = stem.partition(_SEPARATOR)
    if separator:
        _check_description(description)
    return validate_suite_id(id_part)
