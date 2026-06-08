"""Tests for traversal._diagrams — mmdc subprocess renderer utilities."""

from __future__ import annotations

import struct
import subprocess
from unittest.mock import MagicMock, patch

from sync_confluence.traversal._diagrams import (
    extract_png_dimensions,
    find_mmdc,
    make_mermaid_renderer,
    mermaid_attachment_filename,
    render_mermaid_png,
)

_PNG_SIG = b"\x89PNG\r\n\x1a\n"
_WIDTH = 120
_HEIGHT = 80
_IHDR_CHUNK = (
    b"\x00\x00\x00\rIHDR"  # length (13) + "IHDR"
    + struct.pack(">II", _WIDTH, _HEIGHT)
    + b"\x08\x02\x00\x00\x00"  # bit depth, colour type, …
)
_VALID_PNG = _PNG_SIG + _IHDR_CHUNK + b"\x00" * 100
_MMDC = "/usr/bin/mmdc"
_MERMAID_SRC = "graph TD; A-->B"
_SHORT_SRC = "x"
_RUN = "subprocess.run"
_BAD_DATA_LEN = 64
_MMDC_TIMEOUT = 30
_RENDER_PNG_PATH = "sync_confluence.traversal._diagrams.render_mermaid_png"


class TestExtractPngDimensions:
    def test_valid_ihdr(self):
        assert extract_png_dimensions(_VALID_PNG) == (_WIDTH, _HEIGHT)

    def test_bad_signature(self):
        assert extract_png_dimensions(b"\x00" * _BAD_DATA_LEN) is None

    def test_too_short(self):
        assert extract_png_dimensions(_PNG_SIG + b"\x00" * 4) is None


class TestMermaidAttachmentFilename:
    def test_deterministic(self):
        name = mermaid_attachment_filename(_MERMAID_SRC)
        assert name == mermaid_attachment_filename(_MERMAID_SRC)

    def test_png_suffix(self):
        assert mermaid_attachment_filename(_SHORT_SRC).endswith(".png")

    def test_prefix(self):
        assert mermaid_attachment_filename(_SHORT_SRC).startswith("mermaid-")

    def test_different_sources_differ(self):
        assert mermaid_attachment_filename("A") != mermaid_attachment_filename("B")


class TestFindMmdc:
    def test_hint_returned_directly(self):
        assert find_mmdc(_MMDC) == _MMDC

    def test_which_fallback(self):
        with patch("shutil.which", return_value=_MMDC) as mock_which:
            assert find_mmdc() == _MMDC
            mock_which.assert_called_once_with("mmdc")

    def test_not_found(self):
        with patch("shutil.which", return_value=None):
            assert find_mmdc() is None


class TestRenderMermaidPng:
    def test_success_returns_bytes(self):
        proc = MagicMock()
        proc.returncode = 0
        proc.stdout = _VALID_PNG
        with patch(_RUN, return_value=proc) as mock_run:
            rendered = render_mermaid_png(_MERMAID_SRC, _MMDC)
            cmd = mock_run.call_args.args[0]
        assert rendered == _VALID_PNG
        assert "--outputFormat" in cmd
        assert "png" in cmd

    def test_extra_args_forwarded(self):
        proc = MagicMock()
        proc.returncode = 0
        proc.stdout = _VALID_PNG
        with patch(_RUN, return_value=proc) as mock_run:
            render_mermaid_png(_SHORT_SRC, _MMDC, ("--no-sandbox",))
            cmd = mock_run.call_args.args[0]
        assert "--no-sandbox" in cmd

    def test_nonzero_exit_returns_none(self):
        proc = MagicMock()
        proc.returncode = 1
        proc.stderr = b"error"
        with patch(_RUN, return_value=proc):
            assert render_mermaid_png(_SHORT_SRC, _MMDC) is None

    def test_file_not_found_returns_none(self):
        with patch(_RUN, side_effect=FileNotFoundError):
            assert render_mermaid_png(_SHORT_SRC, "/missing/mmdc") is None

    def test_timeout_returns_none(self):
        with patch(
            _RUN,
            side_effect=subprocess.TimeoutExpired(cmd="mmdc", timeout=_MMDC_TIMEOUT),
        ):
            assert render_mermaid_png(_SHORT_SRC, _MMDC) is None


class TestMakeMermaidRenderer:
    def test_returns_rendered_image_on_success(self):
        with patch(
            _RENDER_PNG_PATH,
            return_value=_VALID_PNG,
        ):
            renderer = make_mermaid_renderer(_MMDC)
            rendered = renderer(_MERMAID_SRC)
        assert rendered is not None
        assert rendered.raw_bytes == _VALID_PNG
        assert rendered.content_type == "image/png"
        assert rendered.width == _WIDTH
        assert rendered.height == _HEIGHT

    def test_rendered_image_name_has_png_suffix(self):
        with patch(
            _RENDER_PNG_PATH,
            return_value=_VALID_PNG,
        ):
            renderer = make_mermaid_renderer(_MMDC)
            rendered = renderer(_MERMAID_SRC)
        assert rendered is not None
        assert rendered.name.endswith(".png")

    def test_returns_none_on_render_failure(self):
        with patch(
            _RENDER_PNG_PATH,
            return_value=None,
        ):
            renderer = make_mermaid_renderer(_MMDC)
            assert renderer(_SHORT_SRC) is None

    def test_no_dimensions_when_png_invalid(self):
        with patch(
            _RENDER_PNG_PATH,
            return_value=b"not-a-png",
        ):
            renderer = make_mermaid_renderer(_MMDC)
            rendered = renderer(_SHORT_SRC)
        assert rendered is not None
        assert rendered.width is None
        assert rendered.height is None
