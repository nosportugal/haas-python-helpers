from __future__ import annotations

from sync_confluence.converter import convert_markdown, derive_title

README_FILENAME = "README.md"


class TestConvertMarkdown:
    """Tests for convert_markdown()."""

    def test_plain_paragraph(self):
        output = convert_markdown("Hello world")
        assert "<p>Hello world</p>" in output

    def test_fenced_code_block_with_language(self):
        md = "```python\nprint('hi')\n```"
        output = convert_markdown(md)
        assert 'ac:name="code"' in output
        assert 'ac:name="language">python</ac:parameter>' in output
        assert "print('hi')" in output

    def test_fenced_code_block_without_language(self):
        md = "```\nsome code\n```"
        output = convert_markdown(md)
        assert 'ac:name="code"' in output
        assert "some code" in output

    def test_mermaid_block_without_macro(self):
        md = "```mermaid\ngraph TD;\n```"
        output = convert_markdown(md)
        # Without a mermaid macro name, it renders as a normal code block
        assert 'ac:name="code"' in output
        assert "graph TD;" in output

    def test_mermaid_block_with_macro(self):
        md = "```mermaid\ngraph TD;\n```"
        output = convert_markdown(md, mermaid_macro="mermaid-cloud")
        assert 'ac:name="mermaid-cloud"' in output
        assert "graph TD;" in output

    def test_table_rendering(self):
        md = "| A | B |\n|---|---|\n| 1 | 2 |"
        output = convert_markdown(md)
        assert "<table>" in output
        assert "<td>1</td>" in output

    def test_html_entities_unescaped_in_code(self):
        md = '```python\nif x < 10 and y > 5:\n    print("ok")\n```'
        output = convert_markdown(md)
        # CDATA should contain raw < and >, not &lt; &gt;
        assert "x < 10" in output
        assert "y > 5" in output


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
