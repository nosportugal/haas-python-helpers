from __future__ import annotations

from sync_confluence.converter import convert_markdown


def _body(md: str) -> str:
    return convert_markdown(md).body


_PANEL_INFO = 'ac:name="info"'
_PANEL_NOTE = 'ac:name="note"'
_MARKER_WARNING = "[!WARNING]"


class TestMarkdownFeatures:
    """Tests for the expanded Markdown feature set (Phase 4)."""

    def test_admonition_becomes_panel(self):
        output = _body("!!! tip\n    Use this")
        assert 'ac:name="tip"' in output
        assert "Use this" in output

    def test_github_alert_becomes_panel(self):
        output = _body("> [!WARNING]\n> Careful")
        assert _PANEL_NOTE in output
        assert _MARKER_WARNING not in output
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

    def test_multi_alerts_produce_separate_panels(self):
        output = _body("> [!NOTE]\n> First.\n> [!WARNING]\n> Second.")
        assert _PANEL_INFO in output
        assert _PANEL_NOTE in output
        assert _MARKER_WARNING not in output
        assert "First." in output
        assert "Second." in output


class TestMultiAlerts:
    """Tests for consecutive GitHub-alert blockquote splitting."""

    def test_three_multi_alerts_produce_panels(self):
        output = _body("> [!NOTE]\n> a\n> [!TIP]\n> b\n> [!WARNING]\n> c")
        assert _PANEL_INFO in output
        assert 'ac:name="tip"' in output
        assert _PANEL_NOTE in output
        assert "[!TIP]" not in output
        assert _MARKER_WARNING not in output

    def test_multi_alert_preserves_inline_elems(self):
        output = _body("> [!NOTE]\n> See **bold** text\n> [!WARNING]\n> Second.")
        assert "bold" in output
        assert _PANEL_INFO in output
        assert _PANEL_NOTE in output
        assert _MARKER_WARNING not in output

    def test_multi_alert_unknown_type_as_plain(self):
        output = _body("> [!NOTE]\n> First.\n> [!CUSTOM]\n> Unknown content.")
        assert _PANEL_INFO in output
        assert "Unknown content." in output
        assert "[!CUSTOM]" not in output
