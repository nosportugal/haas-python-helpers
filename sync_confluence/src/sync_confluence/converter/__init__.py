"""Markdown-to-Confluence-Storage-Format conversion.

Public surface (re-exported for backwards compatibility with the previous
single-module layout):

- :func:`convert_markdown` — render Markdown to a CSF fragment.
- :func:`derive_title` — derive a page title from a Markdown file path.
- :class:`ConversionResult`, :class:`ConverterOptions`, :class:`RepoContext`,
  :class:`SourcePaths` — conversion input/output types.
- :class:`RenderedImage`, :class:`MermaidRenderer` — renderer port types.
"""

from sync_confluence.converter._render import convert_markdown
from sync_confluence.converter._result import (
    Attachment,
    ConversionResult,
    ConverterOptions,
    MermaidRenderer,
    RenderedImage,
    RepoContext,
    SourcePaths,
)
from sync_confluence.converter._title import derive_title
from sync_confluence.converter._validate import ConversionError

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
