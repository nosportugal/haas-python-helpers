"""Sync a docs/ directory tree to Confluence Cloud as nested pages.

Mirrors the folder structure under a configured parent page.  ``README.md``
files become section parent pages; other ``.md`` files become leaf pages.
Markdown is converted to Confluence Storage Format with code macros,
optional Mermaid macro support, and relative-link rewriting to GitHub URLs.

Configuration
-------------
Every required value can be provided as a CLI argument **or** an
environment variable.  CLI arguments take precedence.

    CONFLUENCE_URL             Base URL (e.g. https://acme.atlassian.net)
    CONFLUENCE_EMAIL           Atlassian account email
    CONFLUENCE_API_TOKEN       API token from id.atlassian.com
    CONFLUENCE_SPACE_KEY       Target space key
    CONFLUENCE_PARENT_PAGE_ID  Numeric ID of the pre-existing parent page
    CONFLUENCE_ROOT_TITLE      Title for the root page (optional)
    CONFLUENCE_MERMAID_MACRO   Mermaid macro name if plugin installed (optional)
    CONFLUENCE_MANAGED_BY      Label to mark pages owned by this automation;
                               auto-derived from the git repo name if unset
    DOCS_DIR                   Path to docs directory (default: docs)
    GITHUB_REF_NAME            Git ref for link construction (default: main)
    LOG_LEVEL                  Logging verbosity (default: INFO)

Public surface (re-exported from sub-modules):

- :func:`parse_args`, :func:`validate_args` — argument parsing helpers.
- :func:`main` — script entry point.
"""

from sync_confluence.cli._args import parse_args, validate_args
from sync_confluence.cli._main import main

__all__ = ["main", "parse_args", "validate_args"]
