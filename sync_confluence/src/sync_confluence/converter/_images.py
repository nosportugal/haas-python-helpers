"""Transform relative ``<img>`` tags into Confluence attachment images."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from sync_confluence.converter._csf import AC, RI, ElementType, qname
from sync_confluence.converter._naming import attachment_name
from sync_confluence.converter._result import (
    Attachment,
    ConversionResult,
    ConverterOptions,
)

log = logging.getLogger(__name__)

_EXTERNAL_IMG_PREFIXES = ("http://", "https://", "data:")


def _prefer_png(path: Path) -> Path:
    if path.suffix == ".svg":
        png = path.with_suffix(".png")
        if png.is_file():
            return png
    return path


def _resolve_image(src: str, base: Path, docs_root: Optional[Path]) -> Optional[Path]:
    path = (base.parent / src).resolve()
    if docs_root is not None and not path.is_relative_to(docs_root.resolve()):
        log.warning("Image '%s' escapes docs root; leaving unchanged", src)
        return None
    if not path.is_file():
        log.warning("Image '%s' not found; leaving unchanged", src)
        return None
    return _prefer_png(path)


def _to_ac_image(img: ElementType, name: str) -> None:
    image = AC("image")
    alt = img.get("alt")
    if alt:
        image.set(qname("ac", "alt"), alt)
    image.append(RI("attachment", {qname("ri", "filename"): name}))
    image.tail = img.tail
    parent = img.getparent()
    if parent is not None:
        parent.replace(img, image)


def transform_images(
    root: ElementType, options: ConverterOptions, conversion: ConversionResult
) -> None:
    """Rewrite local images to ``ac:image`` and collect them for upload."""
    base = options.paths.current_file
    if base is None:
        return
    for img in list(root.iter("img")):
        src = img.get("src")
        if not src or src.startswith(_EXTERNAL_IMG_PREFIXES):
            continue
        path = _resolve_image(src, base, options.paths.docs_root)
        if path is None:
            continue
        name = attachment_name(path, base.parent)
        conversion.attachments.append(Attachment(path=path, name=name))
        _to_ac_image(img, name)
