"""Construct the configured python-markdown converter."""

from __future__ import annotations

import re
from types import MappingProxyType

import markdown
from pymdownx import emoji

_EXTENSIONS = (
    "tables",
    "fenced_code",
    "toc",
    "md_in_html",
    "admonition",
    "pymdownx.tasklist",
    "pymdownx.caret",
    "pymdownx.tilde",
    "pymdownx.emoji",
)

# Emit emoji as their Unicode character (``to_alt``) instead of CDN images.
_EXTENSION_CONFIGS = MappingProxyType(
    {"pymdownx.emoji": {"emoji_generator": emoji.to_alt}}
)

# python-markdown emits bare boolean attributes (``<input disabled checked>``)
# for task-list checkboxes, which an XML parser rejects.  These are value-ised
# within ``<input>`` tags only, so document text is never touched.
_INPUT_RE = re.compile(r"<input\b([^>]*?)\s*/?>")
_BARE_BOOLEAN_RE = re.compile(r"\b(disabled|checked)\b(?!=)")


def _value_booleans(match: re.Match[str]) -> str:
    attrs = _BARE_BOOLEAN_RE.sub(r'\1="\1"', match.group(1))
    return "<input{0}/>".format(attrs)


def build_markdown() -> markdown.Markdown:
    """Return a fresh python-markdown converter that emits XHTML."""
    return markdown.Markdown(
        extensions=list(_EXTENSIONS),
        extension_configs=dict(_EXTENSION_CONFIGS),
        output_format="xhtml",
    )


def convert_html(text: str) -> str:
    """Render *text* to HTML and value-ise bare boolean input attributes."""
    html = build_markdown().convert(text)
    return _INPUT_RE.sub(_value_booleans, html)
