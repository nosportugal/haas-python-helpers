"""Markdown adapter for the generated-by banner (derives the relative path)."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from sync_confluence.confluence.storage_format import (
    ElementType,
    prepend_generated_by_banner,
)
from sync_confluence.markdown.converter._result import ConverterOptions, SourcePaths


def _relative_path(paths: SourcePaths) -> Optional[Path]:
    if paths.current_file is None:
        return None
    if paths.docs_root is not None:
        try:
            return paths.current_file.relative_to(paths.docs_root)
        except ValueError:
            return Path(paths.current_file.name)
    return Path(paths.current_file.name)


def prepend_markdown_generated_by_banner(
    root: ElementType, options: ConverterOptions
) -> None:
    """Insert the generated-by banner for a converted Markdown page."""
    prepend_generated_by_banner(
        root, options.generated_by, _relative_path(options.paths)
    )
