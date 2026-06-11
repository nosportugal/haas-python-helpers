"""Convert admonitions and GitHub alerts into Confluence panel macros.

Two Markdown forms are recognised:

* the python-markdown ``admonition`` extension (``!!! note``), which renders a
  ``<div class="admonition note">`` block, and
* GitHub alerts (``> [!NOTE]``), which render a blockquote whose first line is
  the alert marker.

Both map onto Confluence ``info``/``tip``/``note``/``warning`` macros.
"""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Optional

from lxml import etree

from sync_confluence.converter._csf import ElementType
from sync_confluence.converter._panels import panel_macro, panel_name
from sync_confluence.converter._tree import move_children, replace_element

_ALERT_RE = re.compile(r"^\s*\[!(\w+)\]\s*\n?")
_MULTI_ALERT_RE = re.compile(r"\[!(\w+)\][ \t]*\n?")
_MIN_MULTI_ALERT_COUNT = 2

# Type aliases to keep annotations within WPS234's complexity limit (max depth 3).
_SegmentList = list[tuple[str, ElementType]]
_RawSegment = tuple[Optional[str], list[str | ElementType]]


def _admonition_title(div: ElementType, kind: str) -> Optional[str]:
    for child in list(div):
        if child.get("class") == "admonition-title":
            text = "".join(child.itertext()).strip()
            div.remove(child)
            return None if text.lower() == kind else text
    return None


def _convert_admonition(div: ElementType) -> None:
    classes = (div.get("class") or "").split()
    kind = next((css for css in classes if css != "admonition"), "note")
    title = _admonition_title(div, kind)
    macro, body = panel_macro(panel_name(kind) or "info", title)
    move_children(div, body)
    replace_element(div, macro)


def _build_p(pieces: list[str | ElementType]) -> ElementType:
    para = etree.Element("p")
    last_elem: Optional[ElementType] = None
    for piece in pieces:
        if isinstance(piece, str):
            if last_elem is None:
                para.text = (para.text or "") + piece
            else:
                last_elem.tail = (last_elem.tail or "") + piece
        else:
            para.append(piece)
            last_elem = piece
    return para


def _segment_alert_p(  # noqa: WPS210, WPS231
    para: ElementType,
) -> Optional[_SegmentList]:
    # WPS210: stateful streaming requires multiple loop-scoped tracking variables.
    # WPS231: marker-splitting algorithm has inherently high cognitive complexity.
    texts = [para.text or ""] + [ch.tail or "" for ch in para]  # noqa: WPS221
    total = sum(len(_MULTI_ALERT_RE.findall(tx)) for tx in texts)
    if total < _MIN_MULTI_ALERT_COUNT:
        return None
    stream: list[str | ElementType] = []
    if para.text:
        stream.append(para.text)
    for child in para:
        child_copy = deepcopy(child)
        tail = child_copy.tail
        child_copy.tail = None
        stream.append(child_copy)
        if tail:
            stream.append(tail)
    current_type: Optional[str] = None
    current_pieces: list[str | ElementType] = []
    segments: list[_RawSegment] = []
    for piece in stream:
        if not isinstance(piece, str):  # noqa: WPS504
            current_pieces.append(piece)
            continue
        rest = piece
        while True:
            match = _MULTI_ALERT_RE.search(rest)
            if match is None:
                if rest:
                    current_pieces.append(rest)
                break
            before = rest[: match.start()]
            if before:
                current_pieces.append(before)
            segments.append((current_type, current_pieces))
            current_type = match.group(1)
            current_pieces = []
            rest = rest[match.end() :]
    segments.append((current_type, current_pieces))
    typed = [(tp, pcs) for tp, pcs in segments if tp is not None]
    if len(typed) < _MIN_MULTI_ALERT_COUNT:
        return None
    return [(tp, _build_p(pcs)) for tp, pcs in typed]


def _replace_with_multiple_panels(  # noqa: WPS210
    blockquote: ElementType,
    segments: list[tuple[str, ElementType]],
) -> None:
    # WPS210: DOM insertion requires tracking parent, index, node list, and
    # per-segment macro/body variables simultaneously.
    parent = blockquote.getparent()
    if parent is None:
        return
    idx = list(parent).index(blockquote)
    nodes_to_insert: list[ElementType] = []
    for type_name, new_p in segments:
        name = panel_name(type_name.lower())
        if name is None:
            nodes_to_insert.append(new_p)
        else:
            macro, body = panel_macro(name, None)
            body.append(new_p)
            nodes_to_insert.append(macro)
    if len(nodes_to_insert) == 0:
        return
    for offset, node in enumerate(nodes_to_insert):
        parent.insert(idx + offset, node)
    nodes_to_insert[-1].tail = blockquote.tail
    parent.remove(blockquote)


def _convert_alert(blockquote: ElementType) -> None:  # noqa: WPS210
    # WPS210: first, marker, name, segments, macro, body = 6 locals (limit 5);
    # adding segments to dispatch multi-alert blocks makes it unavoidable.
    first = blockquote.find("p")
    if first is None:
        return
    marker = _ALERT_RE.match(first.text or "")
    if marker is None:
        return
    name = panel_name(marker.group(1).lower())
    if name is None:
        return
    segments = _segment_alert_p(first)
    if segments is None:
        first.text = _ALERT_RE.sub("", first.text, count=1)
        macro, body = panel_macro(name, None)
        move_children(blockquote, body)
        replace_element(blockquote, macro)
    else:
        _replace_with_multiple_panels(blockquote, segments)


def transform_admonitions(root: ElementType) -> None:
    """Rewrite admonition divs and GitHub-alert blockquotes to panel macros."""
    for div in list(root.iter("div")):
        if "admonition" in (div.get("class") or "").split():
            _convert_admonition(div)
    for blockquote in list(root.iter("blockquote")):
        _convert_alert(blockquote)
