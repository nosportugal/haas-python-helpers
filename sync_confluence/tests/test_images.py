from __future__ import annotations

from sync_confluence.traversal._images import (
    SUPPORTED_LOCAL_IMAGE_EXTENSIONS,
    attachment_content_type,
    extract_local_image_paths,
    local_image_attachment_filename,
)


class TestExtractLocalImagePaths:
    """Tests for extract_local_image_paths()."""

    def test_basic_relative_path(self):
        text = "See ![diagram](images/arch.png) for details."
        assert extract_local_image_paths(text) == ["images/arch.png"]

    def test_dotslash_prefix(self):
        text = "![logo](./assets/logo.png)"
        assert extract_local_image_paths(text) == ["./assets/logo.png"]

    def test_skips_http_url(self):
        text = "![remote](http://example.com/img.png)"
        assert extract_local_image_paths(text) == []

    def test_skips_https_url(self):
        text = "![remote](https://example.com/img.png)"
        assert extract_local_image_paths(text) == []

    def test_skips_anchor(self):
        text = "![anchor](#section)"
        assert extract_local_image_paths(text) == []

    def test_multiple_images(self):
        text = "![a](a.png) and ![b](b.jpg) and ![ext](https://x.com/c.png)"
        paths = extract_local_image_paths(text)
        assert paths == ["a.png", "b.jpg"]

    def test_no_images(self):
        assert extract_local_image_paths("No images here.") == []


class TestLocalImageAttachmentFilename:
    """Tests for local_image_attachment_filename()."""

    def test_nested_path(self):
        assert local_image_attachment_filename("images/logo.png") == "images-logo.png"

    def test_strips_dotslash(self):
        assert local_image_attachment_filename("./assets/fig.jpg") == "assets-fig.jpg"

    def test_flat_filename(self):
        assert local_image_attachment_filename("diagram.png") == "diagram.png"

    def test_deep_nested(self):
        assert local_image_attachment_filename("a/b/c.png") == "a-b-c.png"


class TestAttachmentContentType:
    """Tests for attachment_content_type()."""

    def test_png(self):
        assert attachment_content_type("logo.png") == "image/png"

    def test_jpg(self):
        assert attachment_content_type("photo.jpg") == "image/jpeg"

    def test_jpeg(self):
        assert attachment_content_type("photo.jpeg") == "image/jpeg"

    def test_svg(self):
        assert attachment_content_type("mermaid-abc123.svg") == "image/svg+xml"

    def test_unknown_extension_falls_back(self):
        assert attachment_content_type("file.bin") == "application/octet-stream"

    def test_uppercase_extension(self):
        assert attachment_content_type("IMAGE.PNG") == "image/png"


class TestSupportedLocalImageExtensions:
    def test_svg_not_in_supported_local(self):
        assert ".svg" not in SUPPORTED_LOCAL_IMAGE_EXTENSIONS

    def test_png_and_jpeg_in_supported_local(self):
        assert ".png" in SUPPORTED_LOCAL_IMAGE_EXTENSIONS
        assert ".jpg" in SUPPORTED_LOCAL_IMAGE_EXTENSIONS
        assert ".jpeg" in SUPPORTED_LOCAL_IMAGE_EXTENSIONS
