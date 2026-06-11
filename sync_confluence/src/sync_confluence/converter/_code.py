"""Transform fenced code blocks into Confluence code / diagram macros."""

from __future__ import annotations

import logging
import re
from typing import Optional

from lxml import etree

from sync_confluence.converter._csf import AC, RI, ElementType, qname
from sync_confluence.converter._languages import _PLAIN_TEXT_ALIASES, resolve_language
from sync_confluence.converter._result import (
    Attachment,
    ConversionResult,
    ConverterOptions,
)

log = logging.getLogger(__name__)

_LANGUAGE_CLASS_RE = re.compile(r"language-(\S+)")
_AC = "ac"
_RI = "ri"


def _language_name(code: ElementType) -> Optional[str]:
    class_attr = code.get("class")
    if not class_attr:
        return None
    match = _LANGUAGE_CLASS_RE.search(class_attr)
    return match.group(1) if match else None


def _plain_text_macro(
    macro_name: str, text: str, language: Optional[str] = None
) -> ElementType:
    macro = AC("structured-macro", {qname(_AC, "name"): macro_name})
    if language:
        macro.append(AC("parameter", language, {qname(_AC, "name"): "language"}))
    body = AC("plain-text-body")
    body.text = etree.CDATA(text)
    macro.append(body)
    return macro


def _rendered_image_element(
    attachment: Attachment,
    width: Optional[int] = None,
    height: Optional[int] = None,
) -> ElementType:
    image = AC("image")
    if width is not None:
        image.set(qname(_AC, "width"), str(width))
    if height is not None:
        image.set(qname(_AC, "height"), str(height))
    image.append(RI("attachment", {qname(_RI, "filename"): attachment.name}))
    return image


def _build_macro(
    name: Optional[str],
    text: str,
    options: ConverterOptions,
    conversion: ConversionResult,
) -> ElementType:
    if name == "mermaid" and options.mermaid_renderer is not None:
        rendered = options.mermaid_renderer(text)
        if rendered is not None:
            attachment = Attachment(
                name=rendered.name,
                path=None,
                raw_bytes=rendered.raw_bytes,
                content_type=rendered.content_type,
            )
            conversion.attachments.append(attachment)
            return _rendered_image_element(attachment, rendered.width, rendered.height)
        log.warning("Mermaid renderer returned None; falling back")
    if name == "mermaid" and options.mermaid_macro:
        return _plain_text_macro(options.mermaid_macro, text)
    language = resolve_language(name, force_valid=options.force_valid_language)
    if (
        name
        and language is None
        and name != "mermaid"
        and name.lower() not in _PLAIN_TEXT_ALIASES
    ):
        log.warning("Dropping unsupported code language '%s'", name)
    return _plain_text_macro("code", text, language)


def transform_code_blocks(
    root: ElementType, options: ConverterOptions, conversion: ConversionResult
) -> None:
    """Replace every ``<pre><code>`` block with a Confluence macro."""
    for pre in list(root.iter("pre")):
        code = pre.find("code")
        if code is None:
            continue
        macro = _build_macro(
            _language_name(code), "".join(code.itertext()), options, conversion
        )
        macro.tail = pre.tail
        parent = pre.getparent()
        if parent is not None:
            parent.replace(pre, macro)
