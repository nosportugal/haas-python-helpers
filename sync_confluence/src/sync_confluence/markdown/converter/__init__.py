"""Markdown-to-Confluence-Storage-Format conversion.

Public surface (re-exported for backwards compatibility with the previous
single-module layout):

- :func:`convert_markdown` — render Markdown to a CSF fragment.
- :func:`derive_title` — derive a page title from a Markdown file path.
- :class:`ConversionResult`, :class:`ConverterOptions`, :class:`RepoContext`,
  :class:`SourcePaths` — conversion input/output types.
- :class:`RenderedImage`, :class:`MermaidRenderer` — renderer port types.
"""

from sync_confluence.confluence.storage_format import Attachment, ConversionError
from sync_confluence.markdown.converter._render import convert_markdown
from sync_confluence.markdown.converter._result import (
    ConversionResult,
    ConverterOptions,
    MermaidRenderer,
    RenderedImage,
    RepoContext,
    SourcePaths,
)
from sync_confluence.markdown.converter._title import derive_title

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
