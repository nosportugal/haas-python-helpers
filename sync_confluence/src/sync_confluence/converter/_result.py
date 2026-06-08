"""Input options and output container for Markdown-to-CSF conversion."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Protocol


@dataclass(frozen=True)
class RenderedImage:
    """The output of a successful Mermaid-to-PNG render.

    *name* is the attachment filename (content-hash based); *raw_bytes* are the
    raw PNG bytes; *content_type* is ``"image/png"``; *width* and *height* are
    pixel dimensions extracted from the IHDR chunk (``None`` when unreadable).
    """

    name: str
    raw_bytes: bytes
    content_type: str
    width: Optional[int]
    height: Optional[int]


class MermaidRenderer(Protocol):
    """Callable that converts Mermaid source to a :class:`RenderedImage`."""

    def __call__(self, source: str) -> Optional[RenderedImage]:  # noqa: WPS612, WPS324
        return None  # noqa: WPS324


@dataclass(frozen=True)
class SourcePaths:
    """Filesystem context for the Markdown file being converted.

    *current_file* is the absolute path of the file; *docs_root* is the root
    of the documentation tree (used to resolve image and link targets).
    """

    current_file: Optional[Path] = None
    docs_root: Optional[Path] = None


@dataclass(frozen=True)
class RepoContext:
    """GitHub repository context for the relative-link fallback.

    When a relative link cannot be resolved to an in-scope page, it is
    rewritten to ``{repo_url}/blob/{git_ref}/{path}``.
    """

    repo_url: Optional[str] = None
    git_ref: str = "main"


@dataclass(frozen=True)
class ConverterOptions:
    """Inputs that influence Markdown-to-CSF conversion.

    *doc_index* maps absolute ``.md`` paths to their final Confluence page
    titles; when present, in-scope relative links become native ``ac:link``
    references instead of GitHub URLs.  *generated_by* is the rendered text of
    the auto-generated banner (``None`` omits it).  *force_valid_language*
    drops unknown code-block language tags when ``True``.
    *mermaid_renderer* is an optional callable that converts Mermaid source to
    a PNG attachment; when ``None`` the macro / code-block fallback is used.
    """

    paths: SourcePaths = field(default_factory=SourcePaths)
    repo: RepoContext = field(default_factory=RepoContext)
    doc_index: Optional[dict[Path, str]] = None
    mermaid_macro: Optional[str] = None
    generated_by: Optional[str] = None
    force_valid_language: bool = True
    mermaid_renderer: Optional[MermaidRenderer] = None


@dataclass(frozen=True)
class Attachment:
    """A file to upload alongside a page.

    For local images *path* is the absolute source path; *name* is the
    flattened attachment filename used for the ``ri:filename`` reference and
    the upload.

    For rendered diagrams (e.g. Mermaid PNG) *path* is ``None`` and
    *raw_bytes* / *content_type* carry the in-memory payload.
    """

    name: str
    path: Optional[Path] = None
    raw_bytes: Optional[bytes] = None
    content_type: Optional[str] = None


@dataclass
class ConversionResult:
    """Output of :func:`convert_markdown`.

    *body* is the Confluence Storage Format fragment; *attachments* lists the
    local images referenced by the page, to be uploaded alongside it.
    """

    body: str = ""
    attachments: list[Attachment] = field(default_factory=list)
