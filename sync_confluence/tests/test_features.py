from __future__ import annotations

from sync_confluence.converter import convert_markdown


def _body(md: str) -> str:
    return convert_markdown(md).body


class TestMarkdownFeatures:
    """Tests for the expanded Markdown feature set (Phase 4)."""

    def test_admonition_becomes_panel(self):
        output = _body("!!! tip\n    Use this")
        assert 'ac:name="tip"' in output
        assert "Use this" in output

    def test_github_alert_becomes_panel(self):
        output = _body("> [!WARNING]\n> Careful")
        assert 'ac:name="note"' in output
        assert "[!WARNING]" not in output
        assert "Careful" in output

    def test_task_list_statuses(self):
        output = _body("- [x] done\n- [ ] todo")
        assert "<ac:task-list>" in output
        assert "<ac:task-status>complete</ac:task-status>" in output
        assert "<ac:task-status>incomplete</ac:task-status>" in output

    def test_details_becomes_expand(self):
        body = '<details markdown="1"><summary>More</summary>\nHidden\n</details>'
        output = _body(body)
        assert 'ac:name="expand"' in output
        assert 'ac:name="title">More' in output

    def test_toc_marker_and_double_bracket(self):
        assert 'ac:name="toc"' in _body("[TOC]\n\n# H1")
        assert 'ac:name="toc"' in _body("[[_TOC_]]\n\n# H1")

    def test_emoji_and_sub_superscript(self):
        output = _body("H~2~O x^2^ :smile:")
        assert "<sub>2</sub>" in output
        assert "<sup>2</sup>" in output
        assert "\U0001f604" in output
