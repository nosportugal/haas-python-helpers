from __future__ import annotations

from sync_confluence.converter import (
    ConverterOptions,
    SourcePaths,
    convert_markdown,
)

_PANEL_TAG = 'ac:name="info"'


def _gb_opts(generated_by, tmp_path) -> ConverterOptions:
    md_file = tmp_path / "sub" / "page.md"
    return ConverterOptions(
        paths=SourcePaths(current_file=md_file, docs_root=tmp_path),
        generated_by=generated_by,
    )


class TestGeneratedBy:
    """Tests for the generated-by info panel."""

    def test_default_message(self, tmp_path):
        output = convert_markdown("# H", _gb_opts(None, tmp_path)).body
        assert _PANEL_TAG in output
        assert "auto-generated" in output

    def test_empty_string_suppresses_panel(self, tmp_path):
        output = convert_markdown("# H", _gb_opts("", tmp_path)).body
        assert _PANEL_TAG not in output

    def test_custom_template_substitution(self, tmp_path):
        output = convert_markdown("# H", _gb_opts("Src: %{filepath}", tmp_path)).body
        assert "Src: sub/page.md" in output

    def test_panel_is_first_child(self, tmp_path):
        output = convert_markdown("# Head", _gb_opts(None, tmp_path)).body
        assert output.index(_PANEL_TAG) < output.index("<h1")
