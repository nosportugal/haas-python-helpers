"""Find the folder that blocked a folder creation, and check it may be reused.

Confluence titles are unique per space: a 400/409 on folder creation means a
folder with that title exists somewhere in the space.  It is reused only when
it sits directly under the requested parent.
"""

from __future__ import annotations

from typing import Optional

from atlassian import Confluence

from sync_confluence.confluence._constants import PageSyncAction, _Keys
from sync_confluence.confluence._errors import FolderConflictError
from sync_confluence.confluence._folder_ownership import ensure_folder_owned
from sync_confluence.confluence._logging import log
from sync_confluence.confluence._lookup import (
    _find_folder_by_space_cql,
    find_folder_under_parent,
)
from sync_confluence.confluence._types import FolderUpsertRequest


def _lookup_existing_folder_via_cql(
    confluence: Confluence, request: FolderUpsertRequest
) -> Optional[str]:
    try:
        return _find_folder_by_space_cql(confluence, request.space_key, request.title)
    except Exception as cql_exc:
        log.debug("CQL fallback also failed: %s", cql_exc)
        return None


def _folder_parent_id(confluence: Confluence, folder_id: str) -> Optional[str]:
    """Return the id of the direct parent of *folder_id*, or ``None``."""
    try:
        folder_item = confluence.get(
            path=f"rest/api/content/{folder_id}", params={"expand": "ancestors"}
        )
    except Exception as exc:
        log.debug("Could not read ancestors of folder %s: %s", folder_id, exc)
        return None
    ancestors = (folder_item or {}).get("ancestors") or []
    return str(ancestors[-1][_Keys.ID]) if ancestors else None


def _reuse_fallback_folder(
    confluence: Confluence, request: FolderUpsertRequest, fallback_id: str
) -> tuple[str, str]:
    """Reuse a space-wide match only when it sits directly under the parent."""
    parent_id = _folder_parent_id(confluence, fallback_id)
    if parent_id != str(request.parent_id):
        raise FolderConflictError(
            f"Folder '{request.title}' already exists in space "
            f"{request.space_key} (id={fallback_id}, parent={parent_id}), not "
            f"under parent {request.parent_id}. Titles are unique per space: "
            "rename or move the existing folder."
        )
    ensure_folder_owned(confluence, fallback_id, request)
    log.info("Found existing folder '%s' via CQL (id=%s)", request.title, fallback_id)
    return (fallback_id, PageSyncAction.UNCHANGED)


def find_blocking_folder(
    confluence: Confluence, request: FolderUpsertRequest
) -> Optional[tuple[str, str]]:
    """Return ``(folder_id, "unchanged")`` for a reusable blocking folder.

    Returns ``None`` when no blocking folder is found; raises
    :class:`FolderConflictError` when it exists under another parent.
    """
    fallback_id = _lookup_existing_folder_via_cql(confluence, request)
    if fallback_id is None:
        return None
    return _reuse_fallback_folder(confluence, request, fallback_id)


def find_owned_folder(
    confluence: Confluence, request: FolderUpsertRequest
) -> Optional[str]:
    """Return the id of the folder *request* would reuse, without changing it.

    Read-only counterpart of :func:`upsert_folder` for dry runs: ``None`` when
    no usable folder with that title exists; raises
    :class:`FolderNotOwnedError` or :class:`FolderConflictError` like
    ``upsert_folder`` would, including for a same-titled folder that sits
    under another parent.
    """
    existing = find_folder_under_parent(
        confluence, request.space_key, request.title, request.parent_id
    )
    if existing:
        ensure_folder_owned(confluence, existing[_Keys.ID], request)
        return existing[_Keys.ID]
    blocking = find_blocking_folder(confluence, request)
    return blocking[0] if blocking else None
