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
import shutil
import subprocess
from typing import Optional

from sync_confluence.converter import MermaidRenderer, RenderedImage

log = logging.getLogger(__name__)

_HASH_PREFIX_LEN = 12
_MMDC_TIMEOUT_SECS = 30
_SVG_CONTENT_TYPE = "image/svg+xml"


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
            return RenderedImage(
                name=filename,
                raw_bytes=svg_bytes,
                content_type=_SVG_CONTENT_TYPE,
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
