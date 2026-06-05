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
from typing import Optional

from sync_confluence.converter._csf import ElementType
from sync_confluence.converter._panels import panel_macro, panel_name
from sync_confluence.converter._tree import move_children, replace_element

_ALERT_RE = re.compile(r"^\s*\[!(\w+)\]\s*\n?")


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


def _convert_alert(blockquote: ElementType) -> None:
    first = blockquote.find("p")
    if first is None:
        return
    marker = _ALERT_RE.match(first.text or "")
    if marker is None:
        return
    name = panel_name(marker.group(1).lower())
    if name is None:
        return
    first.text = _ALERT_RE.sub("", first.text, count=1)
    macro, body = panel_macro(name, None)
    move_children(blockquote, body)
    replace_element(blockquote, macro)


def transform_admonitions(root: ElementType) -> None:
    """Rewrite admonition divs and GitHub-alert blockquotes to panel macros."""
    for div in list(root.iter("div")):
        if "admonition" in (div.get("class") or "").split():
            _convert_admonition(div)
    for blockquote in list(root.iter("blockquote")):
        _convert_alert(blockquote)
