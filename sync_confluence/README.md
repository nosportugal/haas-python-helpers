# sync_confluence

Syncs a `docs/` directory tree (or a flat list of Markdown files) to Confluence Cloud as a hierarchy of nested pages.
Subdirectories are mirrored as native Confluence Folders under a configured parent page. The root `README.md` becomes the section parent page; all other `.md` files (including README.md in subfolders) become regular child pages under their respective folder. Markdown is converted to Confluence Storage Format with fenced-code macros, optional Mermaid macro support, and relative-link rewriting to GitHub blob URLs. Content-hash comparison prevents no-op updates, and an optional orphan-cleanup pass deletes pages with no matching source file.

## Package structure

```markdown
python_actions/sync_confluence/
├── src/
│   └── sync_confluence/
│       ├── __init__.py
│       ├── __main__.py
│       ├── cli.py
│       ├── confluence.py
│       ├── converter.py
│       └── traversal.py
├── tests/
│   ├── __init__.py
│   ├── test_cli.py
│   └── test_converter.py
├── pyproject.toml
└── README.md
```

## Prerequisites

- Python 3.11+
- A Confluence Cloud instance with an API token from [id.atlassian.com](https://id.atlassian.com/manage-profile/security/api-tokens)
- A pre-existing parent page — note its numeric page ID (visible in the page URL as `?pageId=…`)

## Installation

Install the package from the repository root:

```sh
pip install python_actions/sync_confluence
```

For local development, install in editable mode:

```sh
pip install -e python_actions/sync_confluence
```

Dependencies (`atlassian-python-api>=3.41.0`, `markdown>=3.7`) are declared in
[`pyproject.toml`](pyproject.toml) and installed automatically.

## Usage

### Dry run (preview, no API calls)

```sh
python -m sync_confluence \
    --url  https://acme.atlassian.net \
    --email user@acme.com \
    --token <api-token> \
    --space DOCS \
    --parent-id 12345 \
    --dry-run
```

### Live sync

```sh
python -m sync_confluence \
  --url  https://acme.atlassian.net \
  --email user@acme.com \
  --token <api-token> \
  --space DOCS \
  --parent-id 12345
```

### Sync a flat list of Markdown files

```sh
python -m sync_confluence \
  --url https://acme.atlassian.net \
  --email user@acme.com \
  --token <api-token> \
  --space DOCS \
  --parent-id 12345 \
  --docs-files intro.md getting-started.md faq.md
```

This mode syncs the specified files as leaf pages directly under the parent page, with no folder structure. Mutually exclusive with `--docs-dir`.

### Orphan cleanup (always active)

**⚠️ WARNING: Every sync run PERMANENTLY DELETES Confluence pages under the parent that do not match a source file. This action is IRREVERSIBLE.**

Orphan cleanup runs automatically after every sync — there is no opt-in flag.
To prevent accidental deletion of unrelated pages, the sync script applies a label to every page it manages.
The label is auto-derived from the git repository name (e.g. `managed-by-a3-e2e`).

- You can override the label with `--managed-by <label>` or the `CONFLUENCE_MANAGED_BY` environment variable.
- **Only pages with this label are eligible for deletion.**
- If the label cannot be derived and `--managed-by` is not set, all unmatched pages under the parent are at risk.

Use `--dry-run` to preview which pages would be deleted before running a live sync.

### Using environment variables

All required values can be supplied as environment variables instead of CLI flags.
Environment variables are useful for CI/CD pipelines where secrets are injected at runtime.

```sh
export CONFLUENCE_URL=https://acme.atlassian.net
export CONFLUENCE_EMAIL=user@acme.com
export CONFLUENCE_API_TOKEN=<api-token>
export CONFLUENCE_SPACE_KEY=DOCS
export CONFLUENCE_PARENT_PAGE_ID=12345

python -m sync_confluence
```

## Configuration reference

CLI flags take precedence over environment variables.
Required flags must be supplied via one of the two mechanisms.

| Flag | Env var | Required | Default | Description |
|---|---|---|---|---|
| `--url` | `CONFLUENCE_URL` | yes | — | Confluence base URL (e.g. `https://acme.atlassian.net`) |
| `--email` | `CONFLUENCE_EMAIL` | yes | — | Atlassian account email |
| `--token` | `CONFLUENCE_API_TOKEN` | yes | — | API token from id.atlassian.com |
| `--space` | `CONFLUENCE_SPACE_KEY` | yes | — | Target space key |
| `--parent-id` | `CONFLUENCE_PARENT_PAGE_ID` | yes | — | Numeric ID of the pre-existing parent page |
| `--docs-dir` | `DOCS_DIR` | no | auto-detect | Path to the directory to sync. If not set, auto-detects the first existing directory from `docs/`, `documentation/`, or `doc/`. |
| `--docs-files` | — | no | — | One or more Markdown files to sync as leaf pages directly under the parent. Mutually exclusive with `--docs-dir`. |
| `--root-title` | `CONFLUENCE_ROOT_TITLE` | no | First H1 in `docs/README.md` | Title for the root section page; mutually exclusive with `--no-root` and `--root-parent` |
| `--managed-by` | `CONFLUENCE_MANAGED_BY` | no | derived from git repository name | Label applied to every page created/updated by this sync; only pages with this label are eligible for orphan deletion |

## Label-based page management

To safely manage and clean up only the pages owned by this repository, the sync script applies a label to every page it creates or updates. The label is auto-derived from the git repository name (e.g. `managed-by-a3-e2e` for this repo). You can override it with `--managed-by <label>` or the `CONFLUENCE_MANAGED_BY` environment variable.

Orphan cleanup runs after every sync. **Only pages with this label are eligible for deletion**, which prevents accidental removal of unrelated or manually created pages under the same parent. If the label cannot be derived and `--managed-by` is not set, all unmatched pages are at risk.

| Flag | Env var | Required | Default | Description |
|---|---|---|---|---|
| `--git-ref` | `GITHUB_REF_NAME` | no | `main` | Git ref used in rewritten GitHub link URLs |
| `--mermaid-macro` | `CONFLUENCE_MERMAID_MACRO` | no | — | Confluence macro name for Mermaid diagrams; omit to render as a plain code block |
| `--dry-run` | — | no | off | Preview pages that would be created, updated, or deleted without making any API calls |

| `--no-root` | — | no | off | Sync all files directly under `--parent-id` without a root container page; mutually exclusive with `--root-parent` and `--root-title` |
| `--root-parent` | `CONFLUENCE_ROOT_PARENT` | no | — | Title of a container folder to find or create under `--parent-id`; all docs are synced under it as children. Always creates a Confluence Folder if not found. Mutually exclusive with `--no-root` and `--root-title` |
| `--log-level` | `LOG_LEVEL` | no | `INFO` | Logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |

## Rename detection

When a Markdown file is renamed, the sync script updates the existing Confluence page in place instead of creating a new page and leaving a stale orphan.

Every page created or updated by the script stores a `sync_confluence_source_path` page property containing its docs-root-relative source file path (e.g. `architecture/stack.md`).
Before each sync, the script builds a `source_path → page_id` map from the existing child pages.
If a file's source path matches a stored property — even when the derived title has changed — the original page is renamed and its content updated rather than creating a duplicate.

In dry-run mode, rename detection is simulated: the script logs which pages would be renamed without making any API changes.

Pages that pre-date this feature and carry no source path property fall back to title-matching only.

## Page edit restrictions

Every synced page is made read-only for everyone except the account whose API token is used for syncing. The script resolves the authenticated user's `accountId` once at startup and applies a `PUT /rest/api/content/{id}/restriction` call after each page creation or update (unchanged pages are skipped to avoid extra API calls).

View access is never restricted — all Confluence users can still read the pages.

**Note:** Until a dedicated bot account is provisioned, this will use the individual user's credentials. Once a bot account is created, update `CONFLUENCE_EMAIL` and `CONFLUENCE_API_TOKEN` to the bot's credentials; the restriction will automatically be transferred to that account on the next sync run.

## Root page modes and folder mapping

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

## Testing

Run the package's test suite from the repository root:

```sh
pytest python_actions/sync_confluence/tests/
```

Or from within the package directory:

```sh
cd python_actions/sync_confluence
pytest
```

Lint with ruff:

```sh
ruff check python_actions/sync_confluence/src/
```

## GitHub Actions integration

The [`docs-sync.yaml`](../../.github/workflows/docs-sync.yaml) workflow triggers on every push to `main` that touches `docs/**`.

```yaml
- name: Install dependencies
  run: pip install python_actions/sync_confluence

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
|---|---|
| `CONFLUENCE_URL` | `https://<tenant>.atlassian.net` |
| `CONFLUENCE_EMAIL` | Atlassian account email |
| `CONFLUENCE_API_TOKEN` | API token from id.atlassian.com |

Required GitHub repository variables (same settings page, `Variables` tab):

| Variable | Value |
|---|---|
| `CONFLUENCE_SPACE_KEY` | Target space key (e.g. `DOCS`) |
| `CONFLUENCE_PARENT_PAGE_ID` | Numeric ID of the pre-existing parent page |

## Module map

| Module | Responsibility |
|---|---|
| [`src/sync_confluence/converter.py`](src/sync_confluence/converter.py) | Markdown → Confluence Storage Format; `convert_markdown`, `derive_title` |
| [`src/sync_confluence/confluence.py`](src/sync_confluence/confluence.py) | Confluence API operations: `upsert_page`, `upsert_folder`, `delete_orphans`, `build_source_path_map`, `_find_page_under_parent`, `_find_folder_under_parent` |
| [`src/sync_confluence/traversal.py`](src/sync_confluence/traversal.py) | Recursive directory walk: `sync_directory`, flat file sync: `sync_files` |
| [`src/sync_confluence/cli.py`](src/sync_confluence/cli.py) | Argument parsing (`parse_args`), validation, `run`, `main` |
| [`src/sync_confluence/__main__.py`](src/sync_confluence/__main__.py) | Package entry point — enables `python -m sync_confluence` |
