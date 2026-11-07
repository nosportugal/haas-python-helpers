"""Deprecated ``sync-confluence`` alias for ``sync-confluence-markdown``."""

from __future__ import annotations

import logging

from sync_confluence.markdown.cli._main import markdown_sync_main

log = logging.getLogger(__name__)


def deprecated_sync_confluence_main() -> None:
    """Warn that the sync-confluence command is deprecated, then run the sync.

    .. deprecated:: 0.2.0
       Use ``sync-confluence-markdown`` instead.
    """
    log.warning(
        "sync-confluence and python -m sync_confluence are deprecated; "
        "use sync-confluence-markdown"
    )
    markdown_sync_main()
