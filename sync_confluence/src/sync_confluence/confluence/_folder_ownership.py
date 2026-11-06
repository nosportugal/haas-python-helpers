"""Refuse to adopt existing folders that this sync did not create."""

from __future__ import annotations

from atlassian import Confluence

from sync_confluence.confluence._errors import FolderNotOwnedError
from sync_confluence.confluence._properties import _page_has_label
from sync_confluence.confluence._types import FolderUpsertRequest


def ensure_folder_owned(
    confluence: Confluence, folder_id: str, request: FolderUpsertRequest
) -> None:
    """Raise :class:`FolderNotOwnedError` if *folder_id* may not be adopted.

    Only checked when ``request.require_ownership`` is set: the existing folder
    must already carry the managed-by label.  Fails closed when no label is
    known, because ownership cannot be proven without one.
    """
    if not request.require_ownership:
        return
    label = request.managed_by_label
    if not label:
        raise FolderNotOwnedError(
            f"Folder '{request.title}' (id={folder_id}) under parent "
            f"{request.parent_id} cannot be adopted: no managed-by label is "
            "available to prove this sync created it. Pass --managed-by."
        )
    if _page_has_label(confluence, folder_id, label):
        return
    raise FolderNotOwnedError(
        f"Folder '{request.title}' (id={folder_id}) under parent "
        f"{request.parent_id} has no '{label}' label, so it was not created by "
        "this sync and will not be adopted. Rename or remove it, or add the "
        "label to adopt it."
    )
