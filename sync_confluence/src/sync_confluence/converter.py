from __future__ import annotations

import html
import re
from pathlib import Path
from typing import Optional

import markdown as md

# ---------------------------------------------------------------------------
# Markdown → Confluence Storage Format
# ---------------------------------------------------------------------------

# Regex for <pre><code class="language-xxx">…</code></pre> blocks produced
# by the markdown fenced_code extension.  DOTALL so the body can span lines.
_CODE_BLOCK_RE = re.compile(
    r'<pre><code class="language-(\w+)">(.*?)</code></pre>',
    re.DOTALL,
)

# Regex for bare <pre><code>…</code></pre> (no language hint).
_CODE_BLOCK_BARE_RE = re.compile(
    r"<pre><code>(.*?)</code></pre>",
    re.DOTALL,
)

# Regex for relative markdown links: [text](path.md) or [text](../path.md#anchor)
# Excludes links that start with http://, https://, or #.
_RELATIVE_LINK_RE = re.compile(r'<a href="(?!https?://|#)([^"]+)">')

_CONFLUENCE_CODE_MACRO = (
    '<ac:structured-macro ac:name="code">'
    '<ac:parameter ac:name="language">{language}</ac:parameter>'
    "<ac:plain-text-body><![CDATA[{code}]]></ac:plain-text-body>"
    "</ac:structured-macro>"
)

_CONFLUENCE_CODE_MACRO_BARE = (
    '<ac:structured-macro ac:name="code">'
    "<ac:plain-text-body><![CDATA[{code}]]></ac:plain-text-body>"
    "</ac:structured-macro>"
)

_CONFLUENCE_MERMAID_MACRO = (
    '<ac:structured-macro ac:name="{macro}">'
    "<ac:plain-text-body><![CDATA[{code}]]></ac:plain-text-body>"
    "</ac:structured-macro>"
)

# ---------------------------------------------------------------------------
# Page title derivation
# ---------------------------------------------------------------------------

_H1_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)


def _unescape_code_body(body: str) -> str:
    """Reverse HTML entity escaping inside code blocks for CDATA wrapping."""
    return html.unescape(body)


def _replace_code_block(match: re.Match, mermaid_macro: Optional[str]) -> str:
    """Replace a fenced code block with a Confluence macro."""
    language = match.group(1)
    code_body = _unescape_code_body(match.group(2))

    if language == "mermaid" and mermaid_macro:
        return _CONFLUENCE_MERMAID_MACRO.format(macro=mermaid_macro, code=code_body)

    return _CONFLUENCE_CODE_MACRO.format(language=language, code=code_body)


def _replace_bare_code_block(match: re.Match) -> str:
    """Replace a bare code block (no language) with a Confluence macro."""
    code_body = _unescape_code_body(match.group(1))
    return _CONFLUENCE_CODE_MACRO_BARE.format(code=code_body)


def _rewrite_relative_link(
    match: re.Match,
    repo_url: str,
    git_ref: str,
    current_file: Path,
) -> str:
    """Rewrite a relative .md link to a GitHub blob URL."""
    href = match.group(1)

    # Split anchor if present
    anchor = ""
    if "#" in href:
        href, anchor = href.rsplit("#", 1)
        anchor = f"#{anchor}"

    # Resolve relative path against the current file's directory
    resolved = (current_file.parent / href).resolve()

    # Try to express relative to CWD (the repo root)
    try:
        repo_path = resolved.relative_to(Path.cwd())
    except ValueError:
        # Cannot resolve — leave link unchanged
        return match.group(0)

    github_url = f"{repo_url}/blob/{git_ref}/{repo_path}{anchor}"
    return f'<a href="{github_url}">'


def convert_markdown(
    text: str,
    *,
    mermaid_macro: Optional[str] = None,
    repo_url: Optional[str] = None,
    git_ref: str = "main",
    current_file: Optional[Path] = None,
) -> str:
    """Convert Markdown text to Confluence Storage Format (XHTML)."""
    converter = md.Markdown(
        extensions=["tables", "fenced_code", "toc", "md_in_html"],
        output_format="html",
    )
    body = converter.convert(text)

    # Post-process: fenced code blocks → Confluence code macros
    body = _CODE_BLOCK_RE.sub(
        lambda match: _replace_code_block(match, mermaid_macro),
        body,
    )
    body = _CODE_BLOCK_BARE_RE.sub(_replace_bare_code_block, body)

    # Post-process: rewrite relative links to GitHub URLs
    if repo_url and current_file:
        body = _RELATIVE_LINK_RE.sub(
            lambda match: _rewrite_relative_link(
                match, repo_url, git_ref, current_file
            ),
            body,
        )

    return body


def _extract_h1_or_none(md_path: Path) -> Optional[str]:
    """Return the first H1 heading text from *md_path*, or ``None``."""
    file_content = md_path.read_text(encoding="utf-8")
    h1_match = _H1_RE.search(file_content)
    return h1_match.group(1).strip() if h1_match else None


def derive_title(md_path: Path, docs_root: Path, root_title: Optional[str]) -> str:
    """Derive a Confluence page title from a markdown file path.

    - Root README.md: use *root_title* or extract the first H1.
    - Other README.md: extract the first H1; fall back to title-casing the
      parent directory name when no H1 is present.
    - Non-README files: extract the first H1; fall back to title-casing the
      file stem when no H1 is present.
    """
    is_readme = md_path.name == "README.md"
    if is_readme and md_path.parent == docs_root:
        return root_title or _extract_h1_or_none(md_path) or "Documentation"
    if is_readme:
        return (
            _extract_h1_or_none(md_path)
            or md_path.parent.name.replace("-", " ").title()
        )
    return _extract_h1_or_none(md_path) or md_path.stem.replace("-", " ").title()
