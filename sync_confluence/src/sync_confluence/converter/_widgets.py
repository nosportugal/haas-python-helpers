"""Convert widget markers (table of contents) into Confluence macros."""

from __future__ import annotations

from sync_confluence.converter._csf import AC, ElementType, qname
from sync_confluence.converter._tree import replace_element


def transform_widgets(root: ElementType) -> None:
    """Rewrite the generated ``[TOC]`` block into a Confluence toc macro."""
    for div in list(root.iter("div")):
        if "toc" in (div.get("class") or "").split():
            macro = AC("structured-macro", {qname("ac", "name"): "toc"})
            replace_element(div, macro)
