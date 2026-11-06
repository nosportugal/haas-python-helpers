"""Sync result accumulator shared by every sync front end."""

from __future__ import annotations

from typing import NamedTuple

from sync_confluence.confluence import PageSyncAction


class SyncResult(NamedTuple):
    """Collected outcome of a sync operation (page map, expected titles, stats)."""

    page_map: dict[str, str]
    expected_titles: set[str]
    expected_paths: set[str]
    skipped: list[str]
    stats: dict[str, int]


def new_sync_result() -> SyncResult:
    """Return an empty sync result with zeroed per-action counters."""
    return SyncResult(
        page_map={},
        expected_titles=set(),
        expected_paths=set(),
        skipped=[],
        stats={
            PageSyncAction.CREATED: 0,
            PageSyncAction.UPDATED: 0,
            PageSyncAction.UNCHANGED: 0,
            PageSyncAction.SKIPPED: 0,
        },
    )
