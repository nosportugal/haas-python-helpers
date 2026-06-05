"""Apply the Confluence Storage Format tree transforms in order."""

from __future__ import annotations

from sync_confluence.converter._admonitions import transform_admonitions
from sync_confluence.converter._blocks import transform_blocks
from sync_confluence.converter._code import transform_code_blocks
from sync_confluence.converter._csf import ElementType
from sync_confluence.converter._generated_by import prepend_generated_by
from sync_confluence.converter._images import transform_images
from sync_confluence.converter._links import transform_links
from sync_confluence.converter._result import ConversionResult, ConverterOptions
from sync_confluence.converter._tasks import transform_tasks
from sync_confluence.converter._widgets import transform_widgets


def transform_tree(
    root: ElementType, options: ConverterOptions, conversion: ConversionResult
) -> None:
    """Run every block, link, image and widget transform over *root*."""
    transform_code_blocks(root, options)
    transform_admonitions(root)
    transform_blocks(root)
    transform_tasks(root)
    transform_widgets(root)
    transform_links(root, options)
    transform_images(root, options, conversion)
    prepend_generated_by(root, options)
