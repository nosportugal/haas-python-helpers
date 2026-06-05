"""Rewrite relative Markdown links.

In-scope ``.md`` targets (present in the document title index) become native
``ac:link`` references resolved by page title; everything else falls back to a
GitHub blob URL (parity with the previous converter).
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from sync_confluence.converter._csf import AC, RI, ElementType, qname
from sync_confluence.converter._result import ConverterOptions

_EXTERNAL_PREFIXES = ("http://", "https://", "#", "mailto:")


def _split_anchor(href: str) -> tuple[str, str]:
    path, _, fragment = href.partition("#")
    return path, fragment


def _resolved_target(href: str, current: Optional[Path]) -> Optional[Path]:
    path, _ = _split_anchor(href)
    if current is None or not path:
        return None
    return (current.parent / path).resolve()


def _github_url(href: str, options: ConverterOptions) -> Optional[str]:
    current = options.paths.current_file
    if not options.repo.repo_url or current is None:
        return None
    path, fragment = _split_anchor(href)
    try:
        repo_path = (current.parent / path).resolve().relative_to(Path.cwd())
    except ValueError:
        return None
    suffix = "#{0}".format(fragment) if fragment else ""
    return "{url}/blob/{ref}/{path}{suffix}".format(
        url=options.repo.repo_url,
        ref=options.repo.git_ref,
        path=repo_path,
        suffix=suffix,
    )


def _to_ac_link(anchor: ElementType, title: str, fragment: str) -> None:
    link = AC("link")
    if fragment:
        link.set(qname("ac", "anchor"), fragment)
    link.append(RI("page", {qname("ri", "content-title"): title}))
    body = AC("link-body")
    body.text = "".join(anchor.itertext())
    link.append(body)
    link.tail = anchor.tail
    parent = anchor.getparent()
    if parent is not None:
        parent.replace(anchor, link)


def _rewrite_link(anchor: ElementType, href: str, options: ConverterOptions) -> None:
    target = _resolved_target(href, options.paths.current_file)
    title = options.doc_index.get(target) if target and options.doc_index else None
    if title is not None:
        _to_ac_link(anchor, title, _split_anchor(href)[1])
        return
    github = _github_url(href, options)
    if github is not None:
        anchor.set("href", github)


def transform_links(root: ElementType, options: ConverterOptions) -> None:
    """Rewrite relative ``<a>`` links to ``ac:link`` or GitHub blob URLs."""
    for anchor in list(root.iter("a")):
        href = anchor.get("href")
        if not href or href.startswith(_EXTERNAL_PREFIXES):
            continue
        _rewrite_link(anchor, href, options)
