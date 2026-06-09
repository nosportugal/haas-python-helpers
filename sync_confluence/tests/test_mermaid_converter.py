"""Tests for Mermaid rendering integration in the converter layer.

Uses a fake :class:`MermaidRenderer` -- no subprocess involved.
"""

from __future__ import annotations

from sync_confluence.converter import (
    ConverterOptions,
    RenderedImage,
    convert_markdown,
)

_MERMAID_MD = "```mermaid\ngraph TD; A-->B\n```\n"
_FAKE_SVG = b"<svg xmlns='http://www.w3.org/2000/svg'><g></g></svg>"
_FAKE_NAME = "mermaid-abc123.svg"
_FAKE_WIDTH = 1280
_AC_IMAGE = "ac:image"
_MACRO_NAME = "mermaid-cloud"


class _FakeRenderer:
    """Fake renderer that always returns a :class:`RenderedImage`."""

    def __init__(self, width: int | None = _FAKE_WIDTH) -> None:
        self._width = width

    def __call__(self, source: str) -> RenderedImage:
        return RenderedImage(
            name=_FAKE_NAME,
            raw_bytes=_FAKE_SVG,
            content_type="image/svg+xml",
            width=self._width,
        )


class _FailingRenderer:
    """Fake renderer that always returns None."""

    def __call__(self, source: str) -> RenderedImage | None:  # noqa: WPS324
        return None  # noqa: WPS324


def _convert(options: ConverterOptions) -> str:
    return convert_markdown(_MERMAID_MD, options).body


def _convert_result(options: ConverterOptions):  # noqa: WPS110
    return convert_markdown(_MERMAID_MD, options)


class TestMermaidConverterWithRenderer:
    def test_renderer_produces_image_body(self):
        options = ConverterOptions(mermaid_renderer=_FakeRenderer())
        body = _convert(options)
        assert _AC_IMAGE in body
        assert _FAKE_NAME in body

    def test_ac_width_emitted_from_intrinsic_width(self):
        options = ConverterOptions(mermaid_renderer=_FakeRenderer())
        body = _convert(options)
        assert 'ac:width="{width}"'.format(width=_FAKE_WIDTH) in body
        assert "ac:height" not in body

    def test_no_ac_width_when_width_unknown(self):
        options = ConverterOptions(mermaid_renderer=_FakeRenderer(width=None))
        body = _convert(options)
        assert _AC_IMAGE in body
        assert "ac:width" not in body

    def test_attachment_added_to_result(self):
        options = ConverterOptions(mermaid_renderer=_FakeRenderer())
        conv = _convert_result(options)
        assert len(conv.attachments) == 1
        att = conv.attachments[0]
        assert att.raw_bytes == _FAKE_SVG
        assert att.name == _FAKE_NAME
        assert att.path is None
        assert att.content_type == "image/svg+xml"

    def test_no_renderer_with_macro_uses_macro(self):
        options = ConverterOptions(mermaid_renderer=None, mermaid_macro=_MACRO_NAME)
        body = _convert(options)
        assert _MACRO_NAME in body
        assert _AC_IMAGE not in body

    def test_no_renderer_no_macro_uses_code_block(self):
        options = ConverterOptions(mermaid_renderer=None, mermaid_macro=None)
        body = _convert(options)
        assert _AC_IMAGE not in body
        assert "structured-macro" in body


class TestMermaidConverterRendererFallback:
    def test_failing_renderer_with_macro_uses_macro(self):
        options = ConverterOptions(
            mermaid_renderer=_FailingRenderer(),  # type: ignore[arg-type]
            mermaid_macro=_MACRO_NAME,
        )
        body = _convert(options)
        assert _MACRO_NAME in body
        assert _AC_IMAGE not in body

    def test_failing_renderer_no_macro_fallback(self):
        options = ConverterOptions(
            mermaid_renderer=_FailingRenderer(),  # type: ignore[arg-type]
            mermaid_macro=None,
        )
        body = _convert(options)
        assert _AC_IMAGE not in body
        assert "structured-macro" in body
