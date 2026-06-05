"""Confluence panel-macro construction and admonition/alert type mapping.

The mapping is stored inverted (target macro -> source keywords) so each macro
name appears once; ``_PANEL_MAP`` is the flattened source -> macro lookup.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Optional

from sync_confluence.converter._csf import AC, ElementType, qname

_PANEL_TYPES = MappingProxyType(
    {
        "info": ("abstract", "example", "info", "note", "question", "quote"),
        "tip": ("hint", "success", "tip"),
        "note": ("attention", "important", "warning"),
        "warning": ("bug", "caution", "danger", "error", "failure"),
    }
)

_PANEL_MAP = MappingProxyType(
    {source: macro for macro, sources in _PANEL_TYPES.items() for source in sources}
)


def panel_name(kind: str) -> Optional[str]:
    """Return the Confluence panel macro name for an admonition/alert *kind*."""
    return _PANEL_MAP.get(kind)


def panel_macro(name: str, title: Optional[str]) -> tuple[ElementType, ElementType]:
    """Return an ``(macro, rich_text_body)`` pair for a panel macro."""
    macro = AC("structured-macro", {qname("ac", "name"): name})
    if title:
        macro.append(AC("parameter", title, {qname("ac", "name"): "title"}))
    body = AC("rich-text-body")
    macro.append(body)
    return macro, body
