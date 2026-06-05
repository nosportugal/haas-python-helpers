"""Confluence Storage Format namespaces and element-construction helpers.

Confluence Storage Format (CSF) is XHTML extended with two namespaces:

* ``ac`` (``http://atlassian.com/content``) for macros and structured content,
* ``ri`` (``http://atlassian.com/resource/identifier``) for resource links.

Stored page bodies use the ``ac:``/``ri:`` prefixes *without* declaring them;
Confluence supplies the declarations implicitly.
"""

from __future__ import annotations

from types import MappingProxyType

from lxml import etree
from lxml.builder import ElementMaker

# lxml exposes its element type only via this name; aliasing keeps annotations
# readable across the package.
ElementType = etree._Element  # noqa: WPS437

AC_NAMESPACE = "http://atlassian.com/content"
RI_NAMESPACE = "http://atlassian.com/resource/identifier"

_NSMAP = MappingProxyType({"ac": AC_NAMESPACE, "ri": RI_NAMESPACE})

AC = ElementMaker(namespace=AC_NAMESPACE, nsmap=dict(_NSMAP))
RI = ElementMaker(namespace=RI_NAMESPACE, nsmap=dict(_NSMAP))


def qname(prefix: str, name: str) -> str:
    """Return the Clark-notation qualified name for ``prefix:name``."""
    return etree.QName(_NSMAP[prefix], name).text
