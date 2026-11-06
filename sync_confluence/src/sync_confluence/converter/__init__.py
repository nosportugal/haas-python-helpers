"""Deprecated import path: use ``sync_confluence.markdown.converter`` instead.

.. deprecated:: 0.2.0
   Removal is planned for 0.3.0.
"""

import warnings

from sync_confluence.markdown.converter import (
    Attachment,
    ConversionError,
    ConversionResult,
    ConverterOptions,
    MermaidRenderer,
    RenderedImage,
    RepoContext,
    SourcePaths,
    convert_markdown,
    derive_title,
)

warnings.warn(
    "sync_confluence.converter is deprecated; "
    "import from sync_confluence.markdown.converter",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = [
    "Attachment",
    "ConversionError",
    "ConversionResult",
    "ConverterOptions",
    "MermaidRenderer",
    "RenderedImage",
    "RepoContext",
    "SourcePaths",
    "convert_markdown",
    "derive_title",
]
