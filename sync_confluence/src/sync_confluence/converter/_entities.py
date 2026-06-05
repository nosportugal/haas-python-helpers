"""Pre-convert named HTML entities so the CSF fragment parses as XML.

python-markdown passes author-written named entities (``&nbsp;``, ``&copy;``,
``&mdash;`` …) through verbatim.  An XML parser rejects every named entity
except the five built-ins, so each is rewritten to a literal character before
parsing.  Characters that are significant in XML are re-encoded as the
corresponding built-in entity, which keeps both text and attribute values
well-formed.
"""

from __future__ import annotations

import re
from html.entities import html5
from types import MappingProxyType

_XML_BUILTINS = frozenset(("amp", "lt", "gt", "quot", "apos"))

_XML_SIGNIFICANT = MappingProxyType(
    {
        "<": "&lt;",
        ">": "&gt;",
        "&": "&amp;",
        '"': "&quot;",
        "'": "&apos;",
    }
)

_ENTITY_RE = re.compile(r"&([0-9A-Za-z]+);")


def _replace_entity(match: re.Match[str]) -> str:
    name = match.group(1)
    if name in _XML_BUILTINS:
        return match.group(0)
    char = html5.get("{0};".format(name))
    if char is None:
        return match.group(0)
    return _XML_SIGNIFICANT.get(char, char)


def escape_named_entities(html_text: str) -> str:
    """Rewrite named HTML entities to characters or XML built-in entities."""
    return _ENTITY_RE.sub(_replace_entity, html_text)
