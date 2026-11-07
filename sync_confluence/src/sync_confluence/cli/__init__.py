"""Deprecated import path: use ``sync_confluence.markdown.cli`` instead.

.. deprecated:: 0.2.0
   Removal is planned for 0.3.0.
"""

import warnings

from sync_confluence.markdown.cli import (
    markdown_sync_main as main,
)
from sync_confluence.markdown.cli import (
    parse_markdown_sync_args as parse_args,
)
from sync_confluence.markdown.cli import validate_args

warnings.warn(
    "sync_confluence.cli is deprecated; import from sync_confluence.markdown.cli",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["main", "parse_args", "validate_args"]
