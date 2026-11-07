"""Confluence code macro (plain-text-body structured macro) builders."""

from __future__ import annotations

from typing import Optional

from lxml import etree

from sync_confluence.confluence.storage_format._csf_namespaces import (
    AC,
    ElementType,
    qname,
)

_AC = "ac"


def build_plain_text_macro(
    macro_name: str, text: str, language: Optional[str] = None
) -> ElementType:
    """Build a structured macro named *macro_name* with a plain-text CDATA body."""
    macro = AC("structured-macro", {qname(_AC, "name"): macro_name})
    if language:
        macro.append(AC("parameter", language, {qname(_AC, "name"): "language"}))
    body = AC("plain-text-body")
    body.text = etree.CDATA(text)
    macro.append(body)
    return macro


def build_code_macro(text: str, language: Optional[str] = None) -> ElementType:
    """Build a Confluence code block macro for *text* with an optional language."""
    return build_plain_text_macro("code", text, language)
