from __future__ import annotations

from pathlib import Path

from sync_confluence.converter import (
    ConverterOptions,
    SourcePaths,
    convert_markdown,
)

_PAGE = "page.md"


def _touch(path: Path) -> None:
    path.write_bytes(b"binary")


def _img_opts(current: Path, docs_root: Path) -> ConverterOptions:
    return ConverterOptions(
        paths=SourcePaths(current_file=current, docs_root=docs_root)
    )


class TestImages:
    """Tests for transform_images()."""

    def test_local_image_becomes_attachment(self, tmp_path):
        _touch(tmp_path / "pic.png")
        rendered = convert_markdown(
            "![cap](pic.png)", _img_opts(tmp_path / _PAGE, tmp_path)
        )
        assert '<ri:attachment ri:filename="pic.png"/>' in rendered.body
        assert [att.name for att in rendered.attachments] == ["pic.png"]

    def test_subdir_image_name_is_flattened(self, tmp_path):
        sub = tmp_path / "images"
        sub.mkdir()
        _touch(sub / "pic.png")
        rendered = convert_markdown(
            "![c](images/pic.png)", _img_opts(tmp_path / _PAGE, tmp_path)
        )
        assert 'ri:filename="images_pic.png"' in rendered.body
        assert rendered.attachments[0].name == "images_pic.png"

    def test_external_image_untouched(self, tmp_path):
        rendered = convert_markdown(
            "![c](https://x/y.png)", _img_opts(tmp_path / _PAGE, tmp_path)
        )
        assert "ac:image" not in rendered.body
        assert not rendered.attachments

    def test_missing_image_left_unchanged(self, tmp_path):
        rendered = convert_markdown(
            "![c](nope.png)", _img_opts(tmp_path / _PAGE, tmp_path)
        )
        assert "ac:image" not in rendered.body
        assert not rendered.attachments

    def test_svg_prefers_sibling_png(self, tmp_path):
        _touch(tmp_path / "d.svg")
        _touch(tmp_path / "d.png")
        rendered = convert_markdown(
            "![c](d.svg)", _img_opts(tmp_path / _PAGE, tmp_path)
        )
        assert rendered.attachments[0].path.name == "d.png"
        assert 'ri:filename="d.png"' in rendered.body
