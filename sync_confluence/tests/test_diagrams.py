from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

from sync_confluence.traversal._diagrams import (
    extract_mermaid_blocks,
    find_mmdc,
    mermaid_attachment_filename,
    render_mermaid_svg,
)

_SUBPROCESS_PATCH = "sync_confluence.traversal._diagrams.subprocess.run"
_WHICH_PATCH = "sync_confluence.traversal._diagrams.shutil.which"
_MMDC_BIN = "/usr/local/bin/mmdc"
_FILE_PERMS = 0o755
_TIMEOUT_SECS = 30

_SVG_BYTES = b"<svg>diagram</svg>"


def _fake_mmdc_run(cmd, **kwargs):  # type: ignore[no-untyped-def]
    """Fake subprocess.run that writes _SVG_BYTES to the -o output path."""
    out_idx = cmd.index("-o") + 1
    Path(cmd[out_idx]).write_bytes(_SVG_BYTES)
    proc = MagicMock()
    proc.returncode = 0
    return proc


class TestExtractMermaidBlocks:
    """Tests for extract_mermaid_blocks()."""

    def test_single_block(self):
        text = "Intro\n\n```mermaid\nflowchart LR\n  A --> B\n```\n\nEnd"
        blocks = extract_mermaid_blocks(text)
        assert blocks == ["flowchart LR\n  A --> B\n"]

    def test_multiple_blocks(self):
        text = "```mermaid\ngraph TD;\n```\n\n```mermaid\nsequenceDiagram\n```\n"
        blocks = extract_mermaid_blocks(text)
        assert len(blocks) == 2
        assert "graph TD;\n" in blocks
        assert "sequenceDiagram\n" in blocks

    def test_no_blocks(self):
        text = "Just some text\n\n```python\nprint('hi')\n```\n"
        assert extract_mermaid_blocks(text) == []

    def test_non_mermaid_fence_not_matched(self):
        text = "```plantuml\n@startuml\n@enduml\n```\n"
        assert extract_mermaid_blocks(text) == []


class TestMermaidAttachmentFilename:
    """Tests for mermaid_attachment_filename()."""

    def test_returns_svg_extension(self):
        filename = mermaid_attachment_filename("flowchart LR\n  A --> B\n")
        assert filename.endswith(".svg")
        assert filename.startswith("mermaid-")

    def test_stable_for_same_source(self):
        source = "graph TD;\n  A --> B;\n"
        assert mermaid_attachment_filename(source) == mermaid_attachment_filename(
            source
        )

    def test_differs_for_different_sources(self):
        assert mermaid_attachment_filename("A --> B") != mermaid_attachment_filename(
            "B --> A"
        )

    def test_filename_length(self):
        # "mermaid-" (8) + 12 hex chars + ".svg" (4) = 24
        filename = mermaid_attachment_filename("x")
        assert len(filename) == 24


class TestRenderMermaidSvg:
    """Tests for render_mermaid_svg()."""

    def test_returns_svg_bytes_on_success(self):
        with patch(_SUBPROCESS_PATCH, side_effect=_fake_mmdc_run):
            svg = render_mermaid_svg("flowchart LR\n  A-->B\n", "/usr/bin/mmdc")
        assert svg == _SVG_BYTES

    def test_returns_none_on_nonzero_exit(self):
        proc = MagicMock()
        proc.returncode = 1
        proc.stderr = b"Error: parse error"
        with patch(_SUBPROCESS_PATCH, return_value=proc):
            svg = render_mermaid_svg("bad diagram", "/usr/bin/mmdc")
        assert svg is None

    def test_returns_none_when_binary_not_found(self):
        with patch(_SUBPROCESS_PATCH, side_effect=FileNotFoundError):
            svg = render_mermaid_svg("graph TD;", "/no/such/mmdc")
        assert svg is None

    def test_returns_none_on_timeout(self):
        exc = subprocess.TimeoutExpired(cmd="mmdc", timeout=_TIMEOUT_SECS)
        with patch(_SUBPROCESS_PATCH, side_effect=exc):
            svg = render_mermaid_svg("graph TD;", "/usr/bin/mmdc")
        assert svg is None


class TestFindMmdc:
    """Tests for find_mmdc()."""

    def test_uses_override_when_executable(self, tmp_path):
        fake_mmdc = tmp_path / "mmdc"
        fake_mmdc.write_text("#!/bin/sh\necho hi")
        fake_mmdc.chmod(_FILE_PERMS)
        found = find_mmdc(str(fake_mmdc))
        assert found == str(fake_mmdc)

    def test_falls_back_when_override_not_found(self):
        with patch(_WHICH_PATCH, return_value=_MMDC_BIN):
            found = find_mmdc("/nonexistent/mmdc")
        assert found == _MMDC_BIN

    def test_detects_mmdc_on_path_when_no_override(self):
        with patch(_WHICH_PATCH, return_value=_MMDC_BIN):
            found = find_mmdc(None)
        assert found == _MMDC_BIN

    def test_returns_none_when_not_found_anywhere(self):
        with patch(_WHICH_PATCH, return_value=None):
            found = find_mmdc(None)
        assert found is None

    def test_none_when_override_missing_no_path(self):
        with patch(_WHICH_PATCH, return_value=None):
            found = find_mmdc("/no/such/binary")
        assert found is None
