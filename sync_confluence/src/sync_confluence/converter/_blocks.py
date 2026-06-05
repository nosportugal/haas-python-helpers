"""Convert ``<details>``/``<summary>`` blocks into Confluence expand macros."""

from __future__ import annotations

from sync_confluence.converter._csf import AC, ElementType, qname
from sync_confluence.converter._tree import move_children, replace_element


def _convert_details(details: ElementType) -> None:
    title = "Details"
    summary = details.find("summary")
    if summary is not None:
        text = "".join(summary.itertext()).strip()
        if text:
            title = text
        details.remove(summary)
    macro = AC("structured-macro", {qname("ac", "name"): "expand"})
    macro.append(AC("parameter", title, {qname("ac", "name"): "title"}))
    body = AC("rich-text-body")
    macro.append(body)
    move_children(details, body)
    replace_element(details, macro)


def transform_blocks(root: ElementType) -> None:
    """Rewrite ``<details>`` blocks into Confluence expand macros."""
    for details in list(root.iter("details")):
        _convert_details(details)
