"""Shared state for the directory walker: result accumulator and config."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple, Optional

from atlassian import Confluence

log = logging.getLogger(__name__)

_ACTION_SKIPPED = "skipped"


class SyncResult(NamedTuple):
    """Collected outcome of a sync operation."""

    page_map: dict[str, str]
    expected_titles: set[str]
    expected_paths: set[str]
    skipped: list[str]
    stats: dict[str, int]


@dataclass
class SyncContext:
    """Encapsulates the Confluence connection and sync configuration."""

    confluence: Confluence
    space_key: str
    docs_root: Path
    root_title: Optional[str] = None
    mermaid_macro: Optional[str] = None
    repo_url: Optional[str] = None
    git_ref: str = "main"
    dry_run: bool = False
    managed_by_label: Optional[str] = None
    restrict_edits_to: Optional[str] = None
    page_width: Optional[str] = None
    upload_attachments: bool = False
    mmdc_path: Optional[str] = (
        None  # resolved path to mmdc binary; None disables mermaid rendering
    )


def _new_sync_result() -> SyncResult:
    return SyncResult(
        page_map={},
        expected_titles=set(),
        expected_paths=set(),
        skipped=[],
        stats={"created": 0, "updated": 0, "unchanged": 0, _ACTION_SKIPPED: 0},
    )


class _SyncRecorder:
    """Accumulates the :class:`SyncResult` for one walk."""

    def __init__(self, docs_root: Path) -> None:
        self._docs_root = docs_root
        self.outcome = _new_sync_result()

    def record_page(
        self,
        source_file: Path,
        title: str,
        page_id: Optional[str],
        action: str,
    ) -> bool:
        """Update *outcome*; return ``True`` on success, ``False`` on skip."""
        if action == _ACTION_SKIPPED:
            self.outcome.skipped.append(title)
            self.outcome.stats[_ACTION_SKIPPED] += 1
            return False
        self.outcome.page_map[str(source_file)] = page_id  # type: ignore[assignment]
        self.outcome.expected_titles.add(title)
        self.outcome.expected_paths.add(str(source_file.relative_to(self._docs_root)))
        self.outcome.stats[action] += 1
        return True

    def record_folder(self, title: str, source_path: str) -> None:
        self.outcome.expected_titles.add(title)
        self.outcome.expected_paths.add(source_path)

    def merge(self, other: SyncResult) -> None:
        self.outcome.page_map.update(other.page_map)
        self.outcome.expected_titles.update(other.expected_titles)
        self.outcome.expected_paths.update(other.expected_paths)
        self.outcome.skipped.extend(other.skipped)
        for stat_key in self.outcome.stats:
            self.outcome.stats[stat_key] += other.stats[stat_key]
