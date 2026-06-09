"""Mermaid-diagram rendering via the ``mmdc`` CLI.

This module is the *concrete* implementation of the :class:`MermaidRenderer`
port defined in :mod:`sync_confluence.converter._result`.  It lives here
(traversal layer) so that ``converter/`` stays pure — no subprocess calls, no
I/O.

Public API
----------
- :func:`find_mmdc` — locate the ``mmdc`` binary.
- :func:`mermaid_attachment_filename` — deterministic content-hash filename.
- :func:`render_mermaid_svg` — call ``mmdc`` and return raw SVG bytes.
- :func:`make_mermaid_renderer` — factory that returns a :class:`MermaidRenderer`
  callable.
"""

from __future__ import annotations

import hashlib
import logging
import re
import shutil
import subprocess
from typing import Optional

from sync_confluence.converter import MermaidRenderer, RenderedImage

log = logging.getLogger(__name__)

_HASH_PREFIX_LEN = 12
_MMDC_TIMEOUT_SECS = 30
_SVG_CONTENT_TYPE = "image/svg+xml"
_MAX_DIAGRAM_DISPLAY_WIDTH = 1800
_NO_DIMS = (None, None)
_SVG_TAG_RE = re.compile(rb"<svg\b[^>]*>", re.IGNORECASE)
_VIEWBOX_DIMS_RE = re.compile(
    r'viewBox\s*=\s*"[^\s"]+\s+[^\s"]+\s+([^\s"]+)\s+([^\s"]+)"'
)
_WIDTH_ATTR_RE = re.compile(rb'\bwidth\s*=\s*"([^"]+)"')
_HEIGHT_ATTR_RE = re.compile(rb'\s+height\s*=\s*"[^"]*"', re.IGNORECASE)
_STYLE_MAX_WIDTH_RE = re.compile(
    rb'\s+style\s*=\s*"[^"]*max-width[^"]*"', re.IGNORECASE
)


def find_mmdc(hint: Optional[str] = None) -> Optional[str]:
    """Return the path to ``mmdc``.

    If *hint* is given it is returned directly (the operator pinned a path).
    Otherwise :func:`shutil.which` is used to search ``$PATH``.
    """
    if hint:
        return hint
    return shutil.which("mmdc")


def mermaid_attachment_filename(source: str) -> str:
    """Return a deterministic attachment filename for *source*.

    The name is ``mermaid-{sha256[:12]}.svg``, which means identical diagrams
    reuse the same attachment slot.
    """
    digest = hashlib.sha256(source.encode()).hexdigest()
    return "mermaid-{digest}.svg".format(digest=digest[:_HASH_PREFIX_LEN])


def render_mermaid_svg(
    source: str,
    mmdc_path: str,
) -> Optional[bytes]:
    """Invoke ``mmdc`` and return the raw SVG bytes.

    *source* is fed via **stdin** (never via a temporary file or argv) to
    avoid shell injection and command-length limits.  Returns ``None`` on any
    failure (non-zero exit, ``FileNotFoundError``, or timeout).
    """
    cmd = [
        mmdc_path,
        "--input",
        "-",
        "--output",
        "-",
        "--outputFormat",
        "svg",
    ]
    try:
        proc = subprocess.run(  # noqa: S603
            cmd,
            input=source.encode(),
            capture_output=True,
            timeout=_MMDC_TIMEOUT_SECS,
        )
    except FileNotFoundError:
        log.warning("mmdc not found at '%s'", mmdc_path)
        return None
    except subprocess.TimeoutExpired:
        log.warning("mmdc timed out while rendering a Mermaid diagram")
        return None
    if proc.returncode != 0:
        log.warning(
            "mmdc exited with code %d: %s",
            proc.returncode,
            proc.stderr.decode(errors="replace"),
        )
        return None
    return proc.stdout


def _display_dimensions(svg_bytes: bytes) -> tuple[Optional[int], Optional[int]]:
    """Return the (width, height) Confluence should display the diagram at.

    The natural size is read from the ``viewBox`` and scaled down so the width
    never exceeds ``_MAX_DIAGRAM_DISPLAY_WIDTH``, preserving the aspect ratio.
    Returns ``_NO_DIMS`` when the size cannot be determined.
    """
    tag = _SVG_TAG_RE.search(svg_bytes)
    if tag is None:
        return _NO_DIMS
    viewbox = _VIEWBOX_DIMS_RE.search(tag.group(0).decode())
    if viewbox is None:
        return _NO_DIMS
    try:
        width, height = (
            round(float(viewbox.group(1))),
            round(float(viewbox.group(2))),
        )
    except ValueError:
        return _NO_DIMS
    if not width or not height:
        return _NO_DIMS
    if width > _MAX_DIAGRAM_DISPLAY_WIDTH:
        height = height * _MAX_DIAGRAM_DISPLAY_WIDTH // width
        width = _MAX_DIAGRAM_DISPLAY_WIDTH
    return (width, height)


def _patch_svg_dimensions(svg_bytes: bytes, width: int, height: int) -> bytes:
    """Rewrite the root ``<svg>`` element to carry explicit pixel dimensions.

    Mermaid renders SVGs with ``width="100%"`` and ``style="max-width:Npx"``.
    Confluence's media pipeline cannot infer intrinsic dimensions from
    percentage widths, leaving the height field blank and reserving a
    default-sized container much taller than the diagram. Setting ``width``
    and ``height`` to the computed display pixel values lets the media
    pipeline populate both dimensions, removing the blank gap.
    """
    tag_match = _SVG_TAG_RE.search(svg_bytes)
    if tag_match is None:
        return svg_bytes
    tag = tag_match.group(0)
    dims = f'width="{width}" height="{height}"'.encode()
    new_tag = _HEIGHT_ATTR_RE.sub(b"", tag)
    if _WIDTH_ATTR_RE.search(new_tag):
        new_tag = _WIDTH_ATTR_RE.sub(dims, new_tag)
    else:
        new_tag = b"".join([new_tag[:-1], b" ", dims, b">"])
    new_tag = _STYLE_MAX_WIDTH_RE.sub(b"", new_tag)
    return svg_bytes.replace(tag, new_tag, 1)


class _MermaidRendererImpl:
    """Stateful callable that renders Mermaid source to a :class:`RenderedImage`.

    Keeps *mmdc_path* bound so it satisfies the :class:`MermaidRenderer`
    Protocol without requiring a nested function.
    """

    def __init__(self, mmdc_path: str) -> None:
        self._mmdc_path = mmdc_path

    def __call__(self, source: str) -> Optional[RenderedImage]:
        svg_bytes = render_mermaid_svg(source, self._mmdc_path)
        if not svg_bytes:
            return None
        width, height = _display_dimensions(svg_bytes)
        if width and height:
            svg_bytes = _patch_svg_dimensions(svg_bytes, width, height)
        return RenderedImage(
            name=mermaid_attachment_filename(source),
            raw_bytes=svg_bytes,
            content_type=_SVG_CONTENT_TYPE,
            width=width,
            height=height,
        )


def make_mermaid_renderer(
    mmdc_path: str,
) -> MermaidRenderer:
    """Return a :class:`MermaidRenderer` bound to *mmdc_path*.

    The returned callable renders Mermaid source to SVG and returns a
    :class:`RenderedImage`.  Returns ``None`` when ``mmdc`` fails or produces
    no bytes.
    """
    return _MermaidRendererImpl(mmdc_path)
