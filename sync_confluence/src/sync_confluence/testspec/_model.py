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
    test_type: str
    vendor: str
    tags: list[str] = field(default_factory=list)
    inputs: Optional[SheetTable] = None
    outputs: Optional[SheetTable] = None

    def page_title(self, suite: str) -> str:
        """Space-unique page title; *suite* keeps workbooks from colliding."""
        return f"{self.test_id} - {self.name} ({self.vendor}, {suite})"


def vendor_folder_title(vendor: str, suite: str) -> str:
    """Space-unique title of the folder holding one vendor's tests of *suite*."""
    return f"{vendor} ({suite})"


def suite_source_prefix(suite: str) -> str:
    """Source-path prefix of every folder and page published for *suite*."""
    return f"testspec/{suite}/"


def vendor_source_path(vendor: str, suite: str) -> str:
    """Source path of a vendor folder; its pages append ``/<test id>``."""
    return f"{suite_source_prefix(suite)}{vendor}"


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
