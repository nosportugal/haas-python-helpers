"""Deprecated import path: use ``sync_confluence.markdown.traversal`` instead.

.. deprecated:: 0.2.0
   Removal is planned for 0.3.0.
"""

import warnings

from sync_confluence.markdown.traversal import (
    SyncContext,
    SyncResult,
    build_doc_index,
    sync_directory,
    sync_files,
)

warnings.warn(
    "sync_confluence.traversal is deprecated; "
    "import from sync_confluence.markdown.traversal",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = [
    "SyncContext",
    "SyncResult",
    "build_doc_index",
    "sync_directory",
    "sync_files",
]
