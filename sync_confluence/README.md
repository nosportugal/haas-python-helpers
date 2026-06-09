# sync_confluence

Syncs a `docs/` directory tree (or a flat list of Markdown files) to Confluence Cloud as a hierarchy of nested pages.

- Subdirectories are mirrored as native Confluence Folders under a configured parent page.
- The root `README.md` becomes the section parent page; all other `.md` files (including `README.md` in subfolders) become regular child pages under their respective folder.
- Markdown is converted to Confluence Storage Format via an lxml pipeline: fenced-code and Mermaid macros, native `ac:link` cross-references, uploaded image attachments, admonitions, task lists, collapsible sections, table-of-contents, emoji and super/subscript.
- Content-hash comparison prevents no-op updates, and an optional orphan-cleanup pass deletes pages with no matching source file.

## Features

- CLI tool for one-way sync of Markdown docs to Confluence Cloud
- Folder mirroring, fenced-code block and Mermaid macro support
- Native internal links: relative `.md` links become `ac:link` page references (preserving `#anchors`); out-of-scope links fall back to GitHub blob URLs
- Image upload: local images are attached to the page and referenced via `ac:image`
- Rich Markdown: admonitions and GitHub alerts (`> [!NOTE]`) become info/tip/note/warning panels; task lists, collapsible `<details>` (expand macro), `[TOC]`/`[[_TOC_]]`, emoji and super/subscript are supported
- Generated-by banner: an info panel is prepended to every page (customizable or suppressible)
- Orphan cleanup with label-based page management — only pages tagged with the managed-by label are eligible for deletion
- Rename detection: renames existing pages in place instead of creating duplicates
- Page edit restrictions: synced pages are set to read-only for everyone except the syncing account
- Python 3.11+ required

## Installation

### Local development

From the repository root:

```bash
pip install -e sync_confluence
```

### CI / consumer repos

```bash
pip install git+https://github.com/nosportugal/haas-python-helpers.git#subdirectory=sync_confluence
```

## Usage

### CLI Example: Dry run (preview, no API calls)

```bash
python -m sync_confluence \
    --url  https://acme.atlassian.net \
    --email user@acme.com \
    --token <api-token> \
    --space DOCS \
    --parent-id 12345 \
    --dry-run
```

### CLI Example: Live sync

```bash
python -m sync_confluence \
  --url  https://acme.atlassian.net \
  --email user@acme.com \
  --token <api-token> \
  --space DOCS \
  --parent-id 12345
```

### CLI Example: Sync a flat list of Markdown files

```bash
python -m sync_confluence \
  --url https://acme.atlassian.net \
  --email user@acme.com \
  --token <api-token> \
  --space DOCS \
  --parent-id 12345 \
  --docs-files intro.md getting-started.md faq.md
```

This mode syncs the specified files as leaf pages directly under the parent page, with no folder structure. Mutually exclusive with `--docs-dir`.

### CLI Example: Using environment variables

```bash
export CONFLUENCE_URL=https://acme.atlassian.net
export CONFLUENCE_EMAIL=user@acme.com
export CONFLUENCE_API_TOKEN=<api-token>
export CONFLUENCE_SPACE_KEY=DOCS
export CONFLUENCE_PARENT_PAGE_ID=12345

python -m sync_confluence
```

### Orphan cleanup (always active)

**⚠️ WARNING: Every sync run PERMANENTLY DELETES Confluence pages under the parent
that do not match a source file. This action is IRREVERSIBLE.**

Orphan cleanup runs automatically after every sync — there is no opt-in flag.
The sync script applies a label (auto-derived from the git repository name,
e.g. `managed-by-a3-e2e`) to every page it manages.
**Only pages with this label are eligible for deletion.**
Override with `--managed-by <label>` or `CONFLUENCE_MANAGED_BY`.
If the label cannot be derived and `--managed-by` is not set,
all unmatched pages under the parent are at risk.

## CLI Arguments & Environment Variables

CLI flags take precedence over environment variables. Required flags must be supplied via one of the two mechanisms.

- `--url` / `CONFLUENCE_URL`: Confluence base URL (e.g. `https://acme.atlassian.net`) — **required**
- `--email` / `CONFLUENCE_EMAIL`: Atlassian account email — **required**
- `--token` / `CONFLUENCE_API_TOKEN`: API token from [id.atlassian.com](https://id.atlassian.com/manage-profile/security/api-tokens) — **required**
- `--space` / `CONFLUENCE_SPACE_KEY`: Target space key — **required**
- `--parent-id` / `CONFLUENCE_PARENT_PAGE_ID`: Numeric ID of the pre-existing parent page — **required**
- `--docs-dir` / `DOCS_DIR`: Path to the docs directory to sync. Auto-detects `docs/`, `documentation/`, or `doc/` if not set
- `--docs-files`: One or more Markdown files to sync as leaf pages directly under the parent. Mutually exclusive with `--docs-dir`
- `--root-title` / `CONFLUENCE_ROOT_TITLE`: Title for the root section page (default: first H1 in `docs/README.md`). Mutually exclusive with `--no-root` and `--root-parent`
- `--no-root`: Sync all files flat under `--parent-id` without a root container page. Mutually exclusive with `--root-parent` and `--root-title`
- `--root-parent` / `CONFLUENCE_ROOT_PARENT`: Title of a container folder to find or create under `--parent-id`. Mutually exclusive with `--no-root` and `--root-title`
- `--managed-by` / `CONFLUENCE_MANAGED_BY`: Label applied to every managed page; only these are eligible for orphan deletion (default: derived from git repository name)
- `--git-ref` / `GITHUB_REF_NAME`: Git ref used in rewritten GitHub link URLs (default: `main`)
- `--mermaid-macro` / `CONFLUENCE_MERMAID_MACRO`: Confluence macro name for Mermaid diagrams; used as a fallback when `mmdc` is unavailable or rendering fails, otherwise omit to fall back to a plain code block
- Mermaid fenced code blocks are rendered to SVG via `mmdc` and attached as Confluence images automatically on every live sync. Skipped in `--dry-run` (the macro or code-block fallback is previewed instead). If `mmdc` is not found a WARNING is emitted and the macro/code-block fallback is used
- Rendered diagrams are sized to their intrinsic dimensions (`ac:width` / `ac:height`, from the SVG `viewBox`, scaled to fit the page) so they use the available width and reserve the correct height instead of Confluence's small or mis-sized default SVG box
- `--mmdc-path` / `MMDC_PATH`: Path to the `mmdc` binary. Defaults to `mmdc` found on `$PATH`
- `--generated-by` / `CONFLUENCE_GENERATED_BY`: Banner text prepended to every page as an info panel. Supports `%{filepath}`, `%{filename}`, `%{filedir}`, `%{filestem}` placeholders. Defaults to a standard auto-generated notice
- `--no-generated-by`: Suppress the auto-generated banner panel
- `--page-width` / `CONFLUENCE_PAGE_WIDTH`: Set display width for every synced page.
  `full-width` renders content across the full browser width; `default` uses the standard Confluence narrow layout.
  Omit to leave page widths unchanged
- `--dry-run`: Preview pages that would be created, updated, or deleted without making any API calls
- `--log-level` / `LOG_LEVEL`: Logging verbosity — `DEBUG`, `INFO`, `WARNING`, `ERROR` (default: `INFO`)

## Root page modes

Three mutually exclusive modes control how the top-level structure is created. At most one of `--root-title`, `--no-root`, and `--root-parent` may be supplied.

**Default** (none of the three flags set):
`docs/README.md` is synced as the root section page directly under `--parent-id`. Its title comes from the first H1 heading in `docs/README.md`, or from `--root-title` if given. All other content is nested below it.

**`--no-root`**:
No root container page is created. All files in the docs directory are synced flat directly under `--parent-id`. `README.md` at the top level is treated as a regular child page.

**`--root-parent TITLE`**:
A named container folder with the given title is found under `--parent-id` (or created if absent). All docs are synced directly under that container folder. The container folder itself has no body and serves purely as a grouping node.

**Folder mapping:**

- Each subdirectory in the docs tree is mirrored as a native Confluence Folder under its parent page or folder.
- The root `README.md` becomes the section parent page (unless `--no-root` is set).
- Any `README.md` inside a subdirectory becomes a regular child page under that folder, not a section parent.
- All other `.md` files become leaf pages under their respective folder or parent.

## Development

- Format: `uv run ruff format .`
- Lint: `uv run ruff check . --fix`
- Tests: `uv run pytest`

Tests must not make real network calls; mock or stub all I/O.

## GitHub Actions integration

Add the following steps to your workflow to sync docs on every push to `main`:

```yaml
- name: Install dependencies
  run: pip install git+https://github.com/nosportugal/haas-python-helpers.git#subdirectory=sync_confluence

- name: Sync to Confluence
  run: |
    python -m sync_confluence \
      --space "${{ vars.CONFLUENCE_SPACE_KEY }}" \
      --parent-id "${{ vars.CONFLUENCE_PARENT_PAGE_ID }}" \
      --git-ref "${{ github.ref_name }}"
  env:
    CONFLUENCE_URL: ${{ secrets.CONFLUENCE_URL }}
    CONFLUENCE_EMAIL: ${{ secrets.CONFLUENCE_EMAIL }}
    CONFLUENCE_API_TOKEN: ${{ secrets.CONFLUENCE_API_TOKEN }}
```

Required GitHub repository secrets (`Settings → Secrets and variables → Actions`):

| Secret | Value |
| --- | --- |
| `CONFLUENCE_URL` | `https://<tenant>.atlassian.net` |
| `CONFLUENCE_EMAIL` | Atlassian account email |
| `CONFLUENCE_API_TOKEN` | API token from id.atlassian.com |

Required GitHub repository variables (same settings page, `Variables` tab):

| Variable | Value |
| --- | --- |
| `CONFLUENCE_SPACE_KEY` | Target space key (e.g. `DOCS`) |
| `CONFLUENCE_PARENT_PAGE_ID` | Numeric ID of the pre-existing parent page |

## License

This package is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
