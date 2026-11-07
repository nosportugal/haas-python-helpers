"""Exceptions raised by the Confluence API wrapper."""

from __future__ import annotations


class FolderConflictError(RuntimeError):
    """A folder with the requested title exists but cannot be used.

    Confluence titles are unique per space, so a folder with the same title
    under a different parent blocks creation; reusing it would publish
    content outside the requested parent (and outside its orphan cleanup).
    """


class FolderNotOwnedError(FolderConflictError):
    """A same-titled folder exists under the parent but lacks the managed-by label.

    Adopting it would label it as managed, making a user-created folder
    eligible for orphan deletion later.
    """
