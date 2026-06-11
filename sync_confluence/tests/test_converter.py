from __future__ import annotations

import pytest

from sync_confluence.converter import (
    ConversionError,
    ConverterOptions,
    convert_markdown,
    derive_title,
)

README_FILENAME = "README.md"
_CODE_MACRO = 'ac:name="code"'
_LANGUAGE_PARAM = 'ac:name="language">'


def _body(md: str, options: ConverterOptions | None = None) -> str:
    return convert_markdown(md, options).body


class TestConvertMarkdown:
    """Tests for convert_markdown()."""

    def test_plain_paragraph(self):
        assert "<p>Hello world</p>" in _body("Hello world")

    def test_fenced_code_block_with_language(self):
        output = _body("```python\nprint('hi')\n```")
        assert _CODE_MACRO in output
        # python is normalised to Confluence's canonical id "py"
        assert f"{_LANGUAGE_PARAM}py</ac:parameter>" in output
        assert "print('hi')" in output

    def test_fenced_code_block_without_language(self):
        output = _body("```\nsome code\n```")
        assert _CODE_MACRO in output
        assert "some code" in output

    def test_mermaid_block_without_macro(self):
        output = _body("```mermaid\ngraph TD;\n```")
        # Without a mermaid macro name, it renders as a normal code block
        assert _CODE_MACRO in output
        assert "graph TD;" in output

    def test_mermaid_block_with_macro(self):
        output = _body(
            "```mermaid\ngraph TD;\n```",
            ConverterOptions(mermaid_macro="mermaid-cloud"),
        )
        assert 'ac:name="mermaid-cloud"' in output
        assert "graph TD;" in output

    def test_table_rendering(self):
        output = _body("| A | B |\n|---|---|\n| 1 | 2 |")
        assert "<table>" in output
        assert "<td>1</td>" in output

    def test_html_entities_unescaped_in_code(self):
        output = _body('```python\nif x < 10 and y > 5:\n    print("ok")\n```')
        # CDATA should contain raw < and >, not &lt; &gt;
        assert "x < 10" in output
        assert "y > 5" in output


class TestConvertMarkdownEdgeCases:
    """Regression tests for converter edge cases."""

    def test_code_block_with_cdata_terminator(self):
        # A literal ]]> inside code must not corrupt the CDATA section.
        output = _body("```\nfoo]]>bar\n```")
        assert "<![CDATA[foo]]]]><![CDATA[>bar" in output

    def test_unknown_language_is_dropped(self):
        output = _body("```nosuchlang\nblah\n```")
        assert _CODE_MACRO in output
        assert "language" not in output
        assert "blah" in output

    def test_named_entities_are_resolved(self):
        output = _body("Copyright &copy; 2026 &mdash; team&nbsp;name")
        assert "&copy;" not in output
        assert "&mdash;" not in output
        assert "\u00a9" in output
        assert "\u2014" in output

    def test_malformed_html_raises_conversion_error(self):
        with pytest.raises(ConversionError):
            convert_markdown('<div markdown="1">\n<span>oops\n</div>')


class TestLanguageAliases:
    """Common fenced-block aliases resolve to Confluence canonical ids."""

    def test_sh_maps_to_shell(self):
        output = _body("```sh\necho hi\n```")
        assert _CODE_MACRO in output
        assert f"{_LANGUAGE_PARAM}shell</ac:parameter>" in output

    def test_yml_maps_to_yaml(self):
        output = _body("```yml\nkey: val\n```")
        assert _CODE_MACRO in output
        assert f"{_LANGUAGE_PARAM}yaml</ac:parameter>" in output

    def test_ts_maps_to_typescript(self):
        output = _body("```ts\nconst x = 1;\n```")
        assert _CODE_MACRO in output
        assert f"{_LANGUAGE_PARAM}typescript</ac:parameter>" in output

    def test_text_alias_produces_no_language(self):
        output = _body("```text\njust text\n```")
        assert "language" not in output
        assert "just text" in output


class TestDeriveTitle:
    """Tests for derive_title()."""

    def test_root_readme_with_explicit_title(self, tmp_path):
        readme = tmp_path / README_FILENAME
        readme.write_text("# Original Heading\n\nContent here.")
        title = derive_title(readme, tmp_path, root_title="Custom Root")
        assert title == "Custom Root"

    def test_root_readme_extracts_h1(self, tmp_path):
        readme = tmp_path / README_FILENAME
        readme.write_text("# My Documentation\n\nContent here.")
        title = derive_title(readme, tmp_path, root_title=None)
        assert title == "My Documentation"

    def test_root_readme_fallback(self, tmp_path):
        readme = tmp_path / README_FILENAME
        readme.write_text("No heading here, just text.")
        title = derive_title(readme, tmp_path, root_title=None)
        assert title == "Documentation"

    def test_subdir_readme_extracts_h1(self, tmp_path):
        subdir = tmp_path / "guides"
        subdir.mkdir()
        readme = subdir / README_FILENAME
        readme.write_text("# User Guides\n\nSome content.")
        title = derive_title(readme, tmp_path, root_title=None)
        assert title == "User Guides"

    def test_subdir_readme_falls_back_to_dirname(self, tmp_path):
        subdir = tmp_path / "my-section"
        subdir.mkdir()
        readme = subdir / "README.md"
        readme.write_text("No heading in this file.")
        title = derive_title(readme, tmp_path, root_title=None)
        assert title == "My Section"

    def test_regular_file_extracts_h1(self, tmp_path):
        md = tmp_path / "setup.md"
        md.write_text("# Setup Instructions\n\nDo this first.")
        title = derive_title(md, tmp_path, root_title=None)
        assert title == "Setup Instructions"

    def test_regular_file_falls_back_to_stem(self, tmp_path):
        md = tmp_path / "getting-started.md"
        md.write_text("No heading, just prose.")
        title = derive_title(md, tmp_path, root_title=None)
        assert title == "Getting Started"
