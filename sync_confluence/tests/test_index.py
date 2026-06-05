from __future__ import annotations

from sync_confluence.traversal import build_doc_index

_README = "README.md"


class TestBuildDocIndex:
    """Tests for the filesystem-only page-title index."""

    def test_maps_files_to_titles(self, tmp_path):
        (tmp_path / _README).write_text("# Ignored Heading")
        (tmp_path / "setup.md").write_text("# Setup Guide")
        files = [tmp_path / _README, tmp_path / "setup.md"]
        index = build_doc_index(tmp_path, "Root Title", files)
        # Root README uses the explicit root title.
        assert index[(tmp_path / _README).resolve()] == "Root Title"
        assert index[(tmp_path / "setup.md").resolve()] == "Setup Guide"

    def test_subdir_readme_uses_h1_not_root_title(self, tmp_path):
        sub = tmp_path / "guides"
        sub.mkdir()
        (sub / _README).write_text("# Guides Section")
        index = build_doc_index(tmp_path, "Root Title", [sub / _README])
        assert index[(sub / _README).resolve()] == "Guides Section"

    def test_duplicate_titles_are_excluded(self, tmp_path):
        (tmp_path / "a.md").write_text("# Same Title")
        (tmp_path / "b.md").write_text("# Same Title")
        files = [tmp_path / "a.md", tmp_path / "b.md"]
        index = build_doc_index(tmp_path, None, files)
        assert (tmp_path / "a.md").resolve() not in index
        assert (tmp_path / "b.md").resolve() not in index
