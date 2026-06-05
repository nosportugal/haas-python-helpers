"""Top-level Markdown-to-CSF conversion entry point."""

from __future__ import annotations

from typing import Optional

from sync_confluence.converter._entities import escape_named_entities
from sync_confluence.converter._markdown import convert_html
from sync_confluence.converter._result import ConversionResult, ConverterOptions
from sync_confluence.converter._transform import transform_tree
from sync_confluence.converter._validate import parse_document, serialize_document


def convert_markdown(
    text: str, options: Optional[ConverterOptions] = None
) -> ConversionResult:
    """Convert Markdown *text* to a Confluence Storage Format fragment.

    Raises :class:`~sync_confluence.converter._validate.ConversionError` when
    the rendered document is not well-formed XML.
    """
    options = options or ConverterOptions()
    html_body = convert_html(text.replace("[[_TOC_]]", "[TOC]"))
    root = parse_document(escape_named_entities(html_body))
    conversion = ConversionResult()
    transform_tree(root, options, conversion)
    conversion.body = serialize_document(root)
    return conversion
