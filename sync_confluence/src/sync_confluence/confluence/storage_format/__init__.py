"""Confluence Storage Format (CSF) XML builders.

Namespaces, document parse/serialize, code macro, generated-by banner and
page attachment.
"""

from sync_confluence.confluence.storage_format._code_macro import (
    build_code_macro,
    build_plain_text_macro,
)
from sync_confluence.confluence.storage_format._csf_document import (
    ConversionError,
    parse_document,
    serialize_document,
)
from sync_confluence.confluence.storage_format._csf_namespaces import (
    AC,
    AC_NAMESPACE,
    RI,
    RI_NAMESPACE,
    ElementType,
    qname,
)
from sync_confluence.confluence.storage_format._generated_by_banner import (
    DEFAULT_GENERATED_BY,
    apply_generated_by_template,
    build_info_panel,
    prepend_generated_by_banner,
)
from sync_confluence.confluence.storage_format._page_attachment import Attachment

__all__ = [
    "AC",
    "AC_NAMESPACE",
    "Attachment",
    "ConversionError",
    "DEFAULT_GENERATED_BY",
    "ElementType",
    "RI",
    "RI_NAMESPACE",
    "apply_generated_by_template",
    "build_code_macro",
    "build_info_panel",
    "build_plain_text_macro",
    "parse_document",
    "prepend_generated_by_banner",
    "qname",
    "serialize_document",
]
