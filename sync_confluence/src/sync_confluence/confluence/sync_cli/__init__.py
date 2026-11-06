"""Shared command-line plumbing for sync front ends.

Confluence connection args, session/auth, managed-by label, sync result,
orphan cleanup and summary.
"""

from sync_confluence.confluence.sync_cli._common_args import (
    add_confluence_connection_args,
    add_page_metadata_args,
)
from sync_confluence.confluence.sync_cli._confluence_session import (
    ConfluenceSession,
    open_confluence_session,
)
from sync_confluence.confluence.sync_cli._env_defaults import env_or_default
from sync_confluence.confluence.sync_cli._finalise_sync_run import finalise_sync_run
from sync_confluence.confluence.sync_cli._repo_detection import (
    detect_repo_url,
    managed_by_label_from_repo_url,
    resolve_managed_by_label,
)
from sync_confluence.confluence.sync_cli._sync_result import (
    SyncResult,
    new_sync_result,
)

__all__ = [
    "ConfluenceSession",
    "SyncResult",
    "add_confluence_connection_args",
    "add_page_metadata_args",
    "detect_repo_url",
    "env_or_default",
    "finalise_sync_run",
    "managed_by_label_from_repo_url",
    "new_sync_result",
    "open_confluence_session",
    "resolve_managed_by_label",
]
