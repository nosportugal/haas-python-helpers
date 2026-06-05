from __future__ import annotations

from pathlib import Path

from sync_confluence.converter import (
    ConverterOptions,
    SourcePaths,
    convert_markdown,
)


def _link_opts(current: Path, index: dict[Path, str]) -> ConverterOptions:
    return ConverterOptions(
        paths=SourcePaths(current_file=current, docs_root=current.parent),
        doc_index=index,
    )


_CURRENT = "a.md"


class TestInternalLinks:
    """Tests for relative-link resolution in transform_links()."""

    def test_in_scope_link_becomes_ac_link(self, tmp_path):
        current = tmp_path / _CURRENT
        index = {(tmp_path / "b.md").resolve(): "Page B"}
        output = convert_markdown("[go](b.md)", _link_opts(current, index)).body
        assert '<ri:page ri:content-title="Page B"/>' in output
        assert "<ac:link-body>go</ac:link-body>" in output

    def test_in_scope_link_preserves_anchor(self, tmp_path):
        current = tmp_path / _CURRENT
        index = {(tmp_path / "b.md").resolve(): "Page B"}
        output = convert_markdown("[go](b.md#sec)", _link_opts(current, index)).body
        assert 'ac:anchor="sec"' in output

    def test_out_of_scope_link_unchanged_without_repo(self, tmp_path):
        current = tmp_path / _CURRENT
        output = convert_markdown("[x](missing.md)", _link_opts(current, {})).body
        assert '<a href="missing.md">x</a>' in output

    def test_external_link_untouched(self, tmp_path):
        current = tmp_path / _CURRENT
        output = convert_markdown("[x](https://e.io)", _link_opts(current, {})).body
        assert '<a href="https://e.io">x</a>' in output
