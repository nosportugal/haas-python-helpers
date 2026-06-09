"""Tests for traversal._diagrams — mmdc subprocess renderer utilities."""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

from sync_confluence.converter import RenderedImage
from sync_confluence.traversal._diagrams import (
    find_mmdc,
    make_mermaid_renderer,
    mermaid_attachment_filename,
    render_mermaid_svg,
)

_MMDC = "/usr/bin/mmdc"
_MERMAID_SRC = "graph TD; A-->B"
_SHORT_SRC = "x"
_FAKE_SVG = b"<svg xmlns='http://www.w3.org/2000/svg'><g></g></svg>"
_RUN = "subprocess.run"
_MMDC_TIMEOUT = 30
_RENDER_SVG_PATH = "sync_confluence.traversal._diagrams.render_mermaid_svg"
_VIEWBOX_WIDTH = 1280
_VIEWBOX_HEIGHT = 720
_VIEWBOX_FLOAT_WIDTH = 1426
_VIEWBOX_FLOAT_HEIGHT = 423
_MAX_DISPLAY_WIDTH = 1800
_SCALED_HEIGHT = 240


def _render_with(svg: bytes) -> RenderedImage:
    with patch(_RENDER_SVG_PATH, return_value=svg):
        image = make_mermaid_renderer(_MMDC)(_MERMAID_SRC)
    assert image is not None
    return image


class TestMermaidAttachmentFilename:
    def test_deterministic(self):
        name = mermaid_attachment_filename(_MERMAID_SRC)
        assert name == mermaid_attachment_filename(_MERMAID_SRC)

    def test_svg_suffix(self):
        assert mermaid_attachment_filename(_SHORT_SRC).endswith(".svg")

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


class TestRenderMermaidSvg:
    def test_success_returns_bytes(self):
        proc = MagicMock()
        proc.returncode = 0
        proc.stdout = _FAKE_SVG
        with patch(_RUN, return_value=proc) as mock_run:
            rendered = render_mermaid_svg(_MERMAID_SRC, _MMDC)
            cmd = mock_run.call_args.args[0]
        assert rendered == _FAKE_SVG
        assert "--outputFormat" in cmd
        assert "svg" in cmd

    def test_nonzero_exit_returns_none(self):
        proc = MagicMock()
        proc.returncode = 1
        proc.stderr = b"error"
        with patch(_RUN, return_value=proc):
            assert render_mermaid_svg(_SHORT_SRC, _MMDC) is None

    def test_file_not_found_returns_none(self):
        with patch(_RUN, side_effect=FileNotFoundError):
            assert render_mermaid_svg(_SHORT_SRC, "/missing/mmdc") is None

    def test_timeout_returns_none(self):
        with patch(
            _RUN,
            side_effect=subprocess.TimeoutExpired(cmd="mmdc", timeout=_MMDC_TIMEOUT),
        ):
            assert render_mermaid_svg(_SHORT_SRC, _MMDC) is None


class TestMakeMermaidRenderer:
    def test_returns_rendered_image_on_success(self):
        with patch(_RENDER_SVG_PATH, return_value=_FAKE_SVG):
            renderer = make_mermaid_renderer(_MMDC)
            rendered = renderer(_MERMAID_SRC)
        assert rendered is not None
        assert rendered.raw_bytes == _FAKE_SVG
        assert rendered.content_type == "image/svg+xml"

    def test_rendered_image_name_has_svg_suffix(self):
        with patch(_RENDER_SVG_PATH, return_value=_FAKE_SVG):
            renderer = make_mermaid_renderer(_MMDC)
            rendered = renderer(_MERMAID_SRC)
        assert rendered is not None
        assert rendered.name.endswith(".svg")

    def test_returns_none_on_render_failure(self):
        with patch(_RENDER_SVG_PATH, return_value=None):
            renderer = make_mermaid_renderer(_MMDC)
            assert renderer(_SHORT_SRC) is None

    def test_idempotent_filename(self):
        """Same source text always produces the same filename."""
        with patch(_RENDER_SVG_PATH, return_value=_FAKE_SVG):
            renderer = make_mermaid_renderer(_MMDC)
            r1 = renderer(_MERMAID_SRC)
            r2 = renderer(_MERMAID_SRC)
        assert r1 is not None
        assert r2 is not None
        assert r1.name == r2.name


class TestDisplayDimensions:
    """Display size parsed from the SVG ``viewBox`` for ``ac:width`` / ``ac:height``."""

    def test_dimensions_parsed_from_viewbox(self):
        rendered = _render_with(b'<svg width="100%" viewBox="0 0 1280 720"></svg>')
        assert rendered.width == _VIEWBOX_WIDTH
        assert rendered.height == _VIEWBOX_HEIGHT

    def test_dimensions_round_viewbox_floats(self):
        rendered = _render_with(b'<svg viewBox="0 0 1426.5 423.2"></svg>')
        assert rendered.width == _VIEWBOX_FLOAT_WIDTH
        assert rendered.height == _VIEWBOX_FLOAT_HEIGHT

    def test_width_capped_and_height_scaled(self):
        rendered = _render_with(b'<svg viewBox="0 0 3000 400"></svg>')
        assert rendered.width == _MAX_DISPLAY_WIDTH
        assert rendered.height == _SCALED_HEIGHT

    def test_no_dimensions_when_viewbox_absent(self):
        rendered = _render_with(b'<svg width="640px" height="480px"></svg>')
        assert rendered.width is None
        assert rendered.height is None

    def test_no_dimensions_for_percentage_only(self):
        rendered = _render_with(_FAKE_SVG)
        assert rendered.width is None
        assert rendered.height is None

    def test_svg_bytes_patched_with_pixel_dimensions(self):
        rendered = _render_with(b'<svg width="100%" viewBox="0 0 1280 720"></svg>')
        assert b'width="1280"' in rendered.raw_bytes
        assert b'height="720"' in rendered.raw_bytes

    def test_percentage_width_removed_from_svg_bytes(self):
        rendered = _render_with(b'<svg width="100%" viewBox="0 0 1280 720"></svg>')
        assert b'width="100%"' not in rendered.raw_bytes
