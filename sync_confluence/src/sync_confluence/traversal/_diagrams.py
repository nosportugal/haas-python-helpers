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
_VIEWBOX_FIELDS = 4
_SVG_TAG_RE = re.compile(rb"<svg\b[^>]*>", re.IGNORECASE)
_VIEWBOX_RE = re.compile(rb'viewBox\s*=\s*"([^"]+)"')
_WIDTH_ATTR_RE = re.compile(rb'\bwidth\s*=\s*"([^"]+)"')


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


def _svg_length_to_int(raw: bytes) -> Optional[int]:
    """Parse an SVG length such as ``b"1426.5"`` or ``b"1426px"`` to ``int``.

    Returns ``None`` for non-pixel values such as ``b"100%"``.
    """
    text = raw.decode(errors="ignore").strip().removesuffix("px").strip()
    try:
        return round(float(text))
    except ValueError:
        return None


def _extract_svg_width(svg_bytes: bytes) -> Optional[int]:
    """Best-effort parse of a Mermaid diagram's intrinsic pixel width.

    Mermaid renders with ``useMaxWidth`` enabled, so the root ``<svg>`` carries
    ``width="100%"`` plus a ``viewBox`` whose third value is the natural width.
    Confluence needs an explicit width to render the attachment at full size
    instead of the tiny default SVG fallback, so the ``viewBox`` width is the
    preferred source and the ``width`` attribute is the fallback. Returns
    ``None`` when no usable pixel width is found.
    """
    tag = _SVG_TAG_RE.search(svg_bytes)
    if tag is None:
        return None
    opening_tag = tag.group(0)
    viewbox = _VIEWBOX_RE.search(opening_tag)
    if viewbox is not None:
        fields = viewbox.group(1).split()
        if len(fields) == _VIEWBOX_FIELDS:
            return _svg_length_to_int(fields[2])
    width_attr = _WIDTH_ATTR_RE.search(opening_tag)
    if width_attr is not None:
        return _svg_length_to_int(width_attr.group(1))
    return None


class _MermaidRendererImpl:
    """Stateful callable that renders Mermaid source to a :class:`RenderedImage`.

    Keeps *mmdc_path* bound so it satisfies the :class:`MermaidRenderer`
    Protocol without requiring a nested function.
    """

    def __init__(self, mmdc_path: str) -> None:
        self._mmdc_path = mmdc_path

    def __call__(self, source: str) -> Optional[RenderedImage]:
        filename = mermaid_attachment_filename(source)
        svg_bytes = render_mermaid_svg(source, self._mmdc_path)
        if svg_bytes:
            width = _extract_svg_width(svg_bytes)
            if width is not None:
                width = min(width, _MAX_DIAGRAM_DISPLAY_WIDTH)
            return RenderedImage(
                name=filename,
                raw_bytes=svg_bytes,
                content_type=_SVG_CONTENT_TYPE,
                width=width,
            )
        return None


def make_mermaid_renderer(
    mmdc_path: str,
) -> MermaidRenderer:
    """Return a :class:`MermaidRenderer` bound to *mmdc_path*.

    The returned callable renders Mermaid source to SVG and returns a
    :class:`RenderedImage`.  Returns ``None`` when ``mmdc`` fails or produces
    no bytes.
    """
    return _MermaidRendererImpl(mmdc_path)
