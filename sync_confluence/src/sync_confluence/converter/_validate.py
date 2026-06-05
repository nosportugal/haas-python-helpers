"""Parse a CSF fragment into an lxml tree and serialize it back.

The fragment emitted by python-markdown is wrapped in a synthetic ``<root>``
element that declares the ``ac``/``ri`` namespaces, parsed as XML (which
validates well-formedness), and serialized back with the wrapper stripped so
the result is a bare Confluence Storage Format fragment.
"""

from __future__ import annotations

import re

from lxml import etree

from sync_confluence.converter._csf import AC_NAMESPACE, RI_NAMESPACE, ElementType

_ROOT_RE = re.compile(r"^<root\b[^>]*>(.*)</root>$", re.DOTALL)


class ConversionError(RuntimeError):
    """Raised when a Markdown document cannot be converted to valid CSF."""


def parse_document(html_fragment: str) -> ElementType:
    """Wrap *html_fragment* in a namespaced root and parse it as XML."""
    parser = etree.XMLParser(
        strip_cdata=False,
        resolve_entities=False,
        no_network=True,
        load_dtd=False,
    )
    document = '<root xmlns:ac="{ac}" xmlns:ri="{ri}">{body}</root>'.format(
        ac=AC_NAMESPACE,
        ri=RI_NAMESPACE,
        body=html_fragment,
    )
    try:
        return etree.fromstring(document, parser=parser)
    except etree.XMLSyntaxError as exc:
        raise ConversionError(str(exc)) from exc


def serialize_document(root: ElementType) -> str:
    """Serialize *root* to a CSF fragment, dropping the synthetic wrapper."""
    xml = etree.tostring(root, encoding="unicode")
    match = _ROOT_RE.match(xml)
    if match is None:
        return ""
    return match.group(1)
