"""Data model for a test-specification workbook."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


class TestSpecError(ValueError):
    """Raised when a workbook does not follow the test-specification layout."""

    __test__ = False


@dataclass
class SheetTable:
    """Header row plus data rows of one worksheet, all cells as text."""

    headers: list[str]
    rows: list[list[str]] = field(default_factory=list)


@dataclass
class TestCase:
    """One row of the Index sheet joined with its Inputs/Outputs sheets."""

    __test__ = False

    test_id: str
    name: str
    description: str
    tags: list[str] = field(default_factory=list)
    # Additional Index columns as (header, value), in table order.
    extra_fields: list[tuple[str, str]] = field(default_factory=list)
    inputs: Optional[SheetTable] = None
    outputs: Optional[SheetTable] = None

    def page_title(self, suite: str) -> str:
        """Space-unique page title; *suite* keeps workbooks from colliding."""
        return f"{self.test_id} - {self.name} ({suite})"

    def source_path(self, suite: str) -> str:
        """Stable identity of the page: ``testspec/<suite>/<test id>``."""
        return f"{suite_source_prefix(suite)}{self.test_id}"


def suite_source_prefix(suite: str) -> str:
    """Source-path prefix of every page published for *suite*."""
    return f"testspec/{suite}/"


def suite_source_path(suite: str) -> str:
    """Source path of the suite folder that holds the pages of *suite*."""
    return f"testspec/{suite}"


@dataclass
class TestSpecSyncConfig:
    """Where to publish the pages and which page metadata to apply."""

    __test__ = False

    space_key: str
    parent_id: str
    source_file: Path
    suite: str
    dry_run: bool = False
    managed_by_label: Optional[str] = None
    restrict_edits_to: Optional[str] = None
    page_width: Optional[str] = None
    generated_by: Optional[str] = None
