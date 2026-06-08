"""Mermaid-diagram rendering via the ``mmdc`` CLI.

This module is the *concrete* implementation of the :class:`MermaidRenderer`
port defined in :mod:`sync_confluence.converter._result`.  It lives here
(traversal layer) so that ``converter/`` stays pure — no subprocess calls, no
I/O.

Public API
----------
- :func:`find_mmdc` — locate the ``mmdc`` binary.
- :func:`mermaid_attachment_filename` — deterministic content-hash filename.
- :func:`extract_png_dimensions` — read width/height from a PNG IHDR chunk.
- :func:`render_mermaid_png` — call ``mmdc`` and return raw PNG bytes.
- :func:`make_mermaid_renderer` — factory that returns a :class:`MermaidRenderer`
  callable.
"""

from __future__ import annotations

import hashlib
import logging
import shutil
import struct
import subprocess
from typing import Optional, Sequence

from sync_confluence.converter import MermaidRenderer, RenderedImage

log = logging.getLogger(__name__)

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_PNG_IHDR_DATA_OFFSET = 16  # signature (8) + length field (4) + "IHDR" (4)
_PNG_DIMENSION_STRUCT = ">II"  # two big-endian unsigned 32-bit ints (W, H)
_HASH_PREFIX_LEN = 12
_MMDC_TIMEOUT_SECS = 30
_PNG_CONTENT_TYPE = "image/png"


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

    The name is ``mermaid-{sha256[:12]}.png``, which means identical diagrams
    reuse the same attachment slot.
    """
    digest = hashlib.sha256(source.encode()).hexdigest()
    return "mermaid-{digest}.png".format(digest=digest[:_HASH_PREFIX_LEN])


def extract_png_dimensions(raw_bytes: bytes) -> Optional[tuple[int, int]]:
    """Extract pixel width and height from a PNG IHDR chunk.

    Returns ``(width, height)`` or ``None`` if *raw_bytes* does not look like
    a valid PNG or the IHDR chunk is too short to read.
    """
    if not raw_bytes.startswith(_PNG_SIGNATURE):
        return None
    end = _PNG_IHDR_DATA_OFFSET + struct.calcsize(_PNG_DIMENSION_STRUCT)
    if len(raw_bytes) < end:
        return None
    width, height = struct.unpack_from(
        _PNG_DIMENSION_STRUCT, raw_bytes, _PNG_IHDR_DATA_OFFSET
    )
    return width, height


def render_mermaid_png(
    source: str,
    mmdc_path: str,
    extra_args: Sequence[str] = (),
) -> Optional[bytes]:
    """Invoke ``mmdc`` and return the raw PNG bytes.

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
        "png",
        "--backgroundColor",
        "transparent",
        "--scale",
        "2",
        *extra_args,
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

    Keeps *mmdc_path* and *extra_args* bound so it satisfies the
    :class:`MermaidRenderer` Protocol without requiring a nested function.
    """

    def __init__(self, mmdc_path: str, extra_args: Sequence[str]) -> None:
        self._mmdc_path = mmdc_path
        self._extra_args = extra_args

    def __call__(self, source: str) -> Optional[RenderedImage]:
        filename = mermaid_attachment_filename(source)
        png_bytes = render_mermaid_png(source, self._mmdc_path, self._extra_args)
        if png_bytes:
            dims = extract_png_dimensions(png_bytes)
            width, height = (None, None) if dims is None else dims
            return RenderedImage(
                name=filename,
                raw_bytes=png_bytes,
                content_type=_PNG_CONTENT_TYPE,
                width=width,
                height=height,
            )
        return None


def make_mermaid_renderer(
    mmdc_path: str,
    extra_args: Sequence[str] = (),
) -> MermaidRenderer:
    """Return a :class:`MermaidRenderer` bound to *mmdc_path*.

    The returned callable renders Mermaid source to PNG, extracts pixel
    dimensions, and returns a :class:`RenderedImage`.  Returns ``None`` when
    ``mmdc`` fails or produces no bytes.
    """
    return _MermaidRendererImpl(mmdc_path, extra_args)
