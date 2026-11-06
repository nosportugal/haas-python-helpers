"""Refuse to adopt existing folders that this sync did not create."""

from __future__ import annotations

from typing import Optional

from atlassian import Confluence

from sync_confluence.confluence._constants import _Keys
from sync_confluence.confluence._errors import FolderNotOwnedError
from sync_confluence.confluence._lookup import find_folder_under_parent
from sync_confluence.confluence._properties import _page_has_label
from sync_confluence.confluence._types import FolderUpsertRequest


def ensure_folder_owned(
    confluence: Confluence, folder_id: str, request: FolderUpsertRequest
) -> None:
    """Raise :class:`FolderNotOwnedError` if *folder_id* may not be adopted.

    Only checked when ``request.require_ownership`` is set and a managed-by
    label is known: the existing folder must already carry that label.
    """
    label = request.managed_by_label
    if not request.require_ownership or not label:
        return
    if _page_has_label(confluence, folder_id, label):
        return
    raise FolderNotOwnedError(
        f"Folder '{request.title}' (id={folder_id}) under parent "
        f"{request.parent_id} has no '{label}' label, so it was not created by "
        "this sync and will not be adopted. Rename or remove it, or add the "
        "label to adopt it."
    )


def find_owned_folder(
    confluence: Confluence, request: FolderUpsertRequest
) -> Optional[str]:
    """Return the id of the folder *request* would reuse, without changing it.

    Read-only counterpart of :func:`upsert_folder` for dry runs: ``None`` when
    no folder with that title is under the parent; raises
    :class:`FolderNotOwnedError` like ``upsert_folder`` would.
    """
    existing = find_folder_under_parent(
        confluence, request.space_key, request.title, request.parent_id
    )
    if not existing:
        return None
    ensure_folder_owned(confluence, existing[_Keys.ID], request)
    return existing[_Keys.ID]
