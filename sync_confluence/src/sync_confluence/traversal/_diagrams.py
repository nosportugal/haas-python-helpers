"""Mermaid diagram extraction and SVG rendering via the mmdc CLI."""

from __future__ import annotations

import hashlib
import logging
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

# Regex to extract the body of ```mermaid ... ``` blocks from raw Markdown.
_MERMAID_BLOCK_RE = re.compile(
    r"^```mermaid\s*\n(.*?)^```",
    re.MULTILINE | re.DOTALL,
)

_HASH_PREFIX_LEN = 12  # first N hex chars of sha256 used as the diagram filename
_MMDC_TIMEOUT = 30  # seconds per diagram render


def extract_mermaid_blocks(text: str) -> list[str]:
    """Return a list of mermaid source bodies found in raw Markdown text.

    Each entry is the raw text between the opening mermaid code fence
    and the closing fence.
    """
    return [blk.group(1) for blk in _MERMAID_BLOCK_RE.finditer(text)]


def mermaid_attachment_filename(source: str) -> str:
    """Return a stable, collision-resistant attachment filename for *source*.

    Format: ``mermaid-<first-12-hex-chars-of-sha256>.svg``
    """
    digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
    short_hash = digest[:_HASH_PREFIX_LEN]
    return f"mermaid-{short_hash}.svg"


def render_mermaid_svg(source: str, mmdc_path: str) -> Optional[bytes]:
    """Render a Mermaid *source* string to SVG bytes using the mmdc CLI.

    Returns ``None`` and logs a warning on any error (non-zero exit, binary
    not found, or timeout).
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        in_path = Path(tmp_dir) / "diagram.mmd"
        out_path = Path(tmp_dir) / "diagram.svg"
        in_path.write_text(source, encoding="utf-8")

        try:
            proc = subprocess.run(
                [
                    mmdc_path,
                    "-i",
                    str(in_path),
                    "-o",
                    str(out_path),
                    "--outputFormat",
                    "svg",
                ],
                capture_output=True,
                timeout=_MMDC_TIMEOUT,
            )
        except FileNotFoundError:
            log.warning("mmdc not found at %s — skipping mermaid render", mmdc_path)
            return None
        except subprocess.TimeoutExpired:
            log.warning(
                "mmdc timed out after %ds rendering a diagram — skipping", _MMDC_TIMEOUT
            )
            return None

        if proc.returncode != 0:
            stderr = proc.stderr.decode("utf-8", errors="replace").strip()
            log.warning(
                "mmdc exited with code %d — skipping mermaid render. stderr: %s",
                proc.returncode,
                stderr,
            )
            return None

        return out_path.read_bytes()


def find_mmdc(mmdc_path_override: Optional[str]) -> Optional[str]:
    """Resolve the path to the mmdc binary.

    If *mmdc_path_override* is provided, verify it is executable and return
    it; log a warning and return ``None`` if it cannot be found.  When no
    override is set, fall back to ``shutil.which("mmdc")``.

    This function is intended to be called **once** at startup so that the
    single warning fires before the sync walk begins.
    """
    if mmdc_path_override:
        candidate = Path(mmdc_path_override)
        if candidate.is_file() and shutil.os.access(candidate, shutil.os.X_OK):  # type: ignore[attr-defined]
            return str(candidate)
        resolved_override = shutil.which(mmdc_path_override)
        if resolved_override:
            return resolved_override
        log.warning(
            "mmdc binary not found at %s — mermaid diagrams will not be rendered",
            mmdc_path_override,
        )
        return None

    resolved = shutil.which("mmdc")
    if resolved:
        return resolved
    log.warning(
        "mmdc not found on PATH — mermaid diagrams will not be rendered. "
        "Install with: npm install -g @mermaid-js/mermaid-cli"
    )
    return None
