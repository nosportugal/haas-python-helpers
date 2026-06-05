"""Shared lxml element-tree helpers."""

from __future__ import annotations

from sync_confluence.converter._csf import ElementType


def replace_element(old: ElementType, new: ElementType) -> None:
    """Replace *old* with *new* in its parent, preserving tail text."""
    new.tail = old.tail
    parent = old.getparent()
    if parent is not None:
        parent.replace(old, new)


def move_children(src: ElementType, dst: ElementType) -> None:
    """Move every child element of *src* into *dst* (appending in order)."""
    for child in list(src):
        dst.append(child)
