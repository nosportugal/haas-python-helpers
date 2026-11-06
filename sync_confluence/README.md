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
- Image upload: local images are attached to the page and referenced via `ac:image`; `.svg` sources with a same-name `.png` sibling automatically use the PNG
- Rich Markdown: admonitions and GitHub alerts (`> [!NOTE]`) become info/tip/note/warning panels; task lists, collapsible `<details>` (expand macro), `[TOC]`/`[[_TOC_]]`, emoji and super/subscript are supported
- Generated-by banner: an info panel is prepended to every page (customizable or suppressible)
- Orphan cleanup with label-based page management — only pages tagged with the managed-by label are eligible for deletion (see [Orphan cleanup](#orphan-cleanup-always-active) for the full warning)
- Rename detection: renames existing pages in place instead of creating duplicates
- Page edit restrictions: synced pages are set to read-only for everyone except the syncing account (always applied; no opt-out flag — if the Confluence API cannot return an `accountId` for the authenticating user the sync aborts before touching any pages)
- Image upload: `.svg` images with a same-name `.png` sibling use the PNG automatically
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

### CLI Example: Sync docs

Add `--dry-run` to preview what would be created, updated, or deleted without making any API calls.

```bash
sync-confluence-markdown \
  --url  https://acme.atlassian.net \
  --email user@acme.com \
  --token <api-token> \
  --space DOCS \
  --parent-id 12345
```

### CLI Example: Sync a flat list of Markdown files

```bash
sync-confluence-markdown \
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

sync-confluence-markdown
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
- `--mermaid-macro` / `CONFLUENCE_MERMAID_MACRO`: Confluence macro name used as the secondary Mermaid fallback. Priority order: (1) render via `mmdc` to SVG; (2) emit this macro if set; (3) fall back to a plain code block. Omit this flag when you have no Confluence Mermaid macro installed
- Mermaid fenced code blocks are rendered to SVG via `mmdc` and attached as Confluence images automatically on every live sync. Skipped in `--dry-run` (the macro or code-block fallback is previewed instead). If `mmdc` is not found a WARNING is emitted and the fallback chain (macro → code block) applies
- Rendered diagrams are sized to their intrinsic dimensions (`ac:width` / `ac:height`, from the SVG `viewBox`, scaled to fit the page) so they use the available width and reserve the correct height instead of Confluence's small or mis-sized default SVG box
- `--mmdc-path` / `MMDC_PATH`: Path to the `mmdc` binary. Defaults to `mmdc` found on `$PATH`
- `--generated-by` / `CONFLUENCE_GENERATED_BY`: Banner text prepended to every page as an info panel. Supports `%{filepath}`, `%{filename}`, `%{filedir}`, `%{filestem}` placeholders.
  Defaults to a standard auto-generated notice. Setting `CONFLUENCE_GENERATED_BY=` (empty string) suppresses the banner without needing `--no-generated-by`
- `--no-generated-by`: Suppress the auto-generated banner panel
- `--page-width` / `CONFLUENCE_PAGE_WIDTH`: Set display width for every synced page.
  `full-width` renders content across the full browser width; `default` uses the standard Confluence narrow layout.
  Omit to leave page widths unchanged. Invalid values are rejected, including from the environment variable
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

## Test specifications from Excel (`sync-confluence-testspec`)

Publishes a test-specification workbook (`.xlsx`) as one Confluence page per test case.
All pages of a workbook are listed in one **suite folder** under `--parent-id`. Requires
the `xlsx` extra:

```bash
pip install "sync-confluence[xlsx] @ git+https://github.com/nosportugal/haas-python-helpers.git#subdirectory=sync_confluence"

sync-confluence-testspec --xlsx testspec.xlsx --space HaaS --parent-id 12345 --dry-run
```

A ready-made example that follows this format is in
[`examples/testspec_format_example.xlsx`](examples/testspec_format_example.xlsx).

### Workbook format

The format is the same for any kind of test (unit, integration, E2E, ...). Headers are
matched case-insensitively; the first non-empty row of each sheet is the header row.

| Sheet            | Required | Content                                                                                                  |
| ---------------- | -------- | -------------------------------------------------------------------------------------------------------- |
| **First sheet**  | yes      | The **Index**: one row per test case. Its name is not significant                                        |
| `<ID> - Inputs`  | no       | A table with any columns, shown as-is on the page of the test with that `ID`                             |
| `<ID> - Outputs` | no       | A table with any columns, shown as-is on the page of the test with that `ID`                             |

No other sheet is allowed (see [Rejected sheets](#rejected-sheets)).

`Inputs` and `Outputs` sheets have **no required columns and no value rules**: the team that
writes the test cases decides what they hold, for example a column of full JSON documents, a
column of partial JSON, or a `Parameter | Value` table. The tool only renders the table as
written: the first row is the header, every following row is a row, and line breaks inside a
cell are kept. Cell text is shown as plain text, so indentation inside a cell is not preserved.
Empty columns at the right are dropped; a column that holds data is always kept, even if its
header is blank.

#### Index sheet

The first sheet is always the Index. Its header row must contain these **mandatory
columns**; a missing one fails the run:

| Column        | Meaning                                                                                                      |
| ------------- | ------------------------------------------------------------------------------------------------------------ |
| `ID`          | Test identifier: dot-separated numbers with **any number of levels** (`1`, `1.1`, `1.1.3`), unique in the workbook. Format the column as **Text** so `1.10` is not read as `1.1`. Tests are ordered numerically, level by level |
| `Name`        | Short test name (required on every row)                                                                      |
| `Description` | What the test checks; may be empty on a row. A blank line starts a new paragraph                             |
| `Tags`        | Free-form tags separated by `;` or `,`; may be empty on a row. Tags are also applied as page labels         |

Any **other column** is an additional column. Additional columns have no special meaning
and no value rules: they are handled all alike, and their header is used as the field name
on the page. Their position in the table sets their order on the page. Headers must not be
blank or repeated.

#### Page layout

```text
Tags: <tags>
<additional column 1>: <value>
<additional column 2>: <value>
...
Description
Inputs
Outputs
```

`Tags` is always the first field, then the additional columns in the order they appear in
the Index table, then `Description`, `Inputs` and `Outputs`. Fields with no value show `-`.
Missing `Inputs`/`Outputs` sheets render as "Not specified yet.". An Index without test cases
also fails the run. The workbook is fully validated before any Confluence call.

#### Rejected sheets

A sheet other than the Index, `<ID> - Inputs` and `<ID> - Outputs` fails the run, so a
mistyped name can never silently drop its content. `<ID>` must be listed in the Index; the
match ignores case and surrounding spaces. The error names each sheet and says why:

| Sheet name       | Reason reported                                                    |
| ---------------- | ------------------------------------------------------------------ |
| `1.1.3 - Inputs` | refers to ID `1.1.3`, which is not in the Index                    |
| `1.1- Inputs`    | must be named exactly `1.1 - Inputs`                               |
| `Notes`          | is neither the Index (first sheet) nor named `<ID> - Inputs`/`Outputs` |

The message always ends with the list of IDs found in the Index.

### Titles, folders and cleanup

Confluence titles are unique per space, so titles carry a **suite** name (`--suite`, default:
the workbook file name without extension; a naming rule for workbook files is still to be
defined). The suite folder is titled `<suite>` and each page `<ID> - <Name> (<suite>)`.
Labels are added, never removed, when tags change.

`sync-confluence-testspec` accepts the connection, `--dry-run`, `--managed-by`, `--log-level`,
`--page-width`, `--generated-by` and `--no-generated-by` options described above, plus:

- `--xlsx` / `TESTSPEC_XLSX`: Path to the workbook — **required**
- `--suite` / `TESTSPEC_SUITE`: Suite name used in titles and to scope cleanup (default: workbook file name without extension). Must not contain `/`

The default managed-by label is `managed-by-<repo>-testspec`, separate from the Markdown sync's
`managed-by-<repo>`, so both commands can share a `--parent-id` without deleting each other's pages.
An explicit `--managed-by` is used as given.

Orphan cleanup only considers pages of the **same suite** (stored source path
`testspec/<suite>/...`): those under `--parent-id` that are no longer in the workbook are
**permanently deleted**, while other workbooks synced to the same parent are left alone.
If the suite folder title already exists elsewhere in the space, the run fails without cleanup
instead of publishing under the other parent. An existing suite folder under `--parent-id` is
only reused when it already carries the managed-by label; a folder someone created by hand with
the same title fails the run instead of being adopted (and later becoming eligible for deletion).
Add the label to the folder to adopt it deliberately. In both commands cleanup is
skipped for the whole run when any page was skipped (title collision), so a page that could not
be moved is never deleted.

## Deprecated aliases

Deprecated in 0.2.0, removal planned for 0.3.0 — migrate to `sync-confluence-markdown`:

- the `sync-confluence` command and `python -m sync_confluence` (they log a deprecation warning, then run `sync-confluence-markdown`);
- the `sync_confluence.cli`, `sync_confluence.converter` and `sync_confluence.traversal` import paths (use `sync_confluence.markdown.cli`, `.converter` and `.traversal`).

## Package layout

```text
sync_confluence/
├── confluence/                  shared Confluence API (pages, folders, labels, cleanup)
│   ├── storage_format/          Confluence Storage Format (CSF) XML builders; stdlib + lxml only
│   └── sync_cli/                shared command-line plumbing (args, session, orphan cleanup, sync result)
├── markdown/                    sync-confluence-markdown  (converter/, traversal/, cli/)
└── testspec/                    sync-confluence-testspec
```

Lower layers never import higher ones; `tests/test_layout.py` enforces this.
Front ends import shared code from package level (`sync_confluence.confluence[.storage_format|.sync_cli]`), never from another subpackage's `_private` module.

## Development

First-time setup:

```bash
pip install -e sync_confluence
pre-commit install
```

Validation (run from the repository root after every change):

```bash
pre-commit run --files $(git diff --name-only HEAD; git ls-files --others --exclude-standard)
cd sync_confluence && pytest
```

If `pre-commit` auto-fixes any file, re-run the `pre-commit` command before committing.

Tests must not make real network calls; mock or stub all I/O.

## GitHub Actions integration

Add the following steps to your workflow to sync docs on every push to `main`:

```yaml
- name: Install dependencies
  run: pip install git+https://github.com/nosportugal/haas-python-helpers.git#subdirectory=sync_confluence

- name: Sync to Confluence
  run: |
    sync-confluence-markdown \
      --space "${{ vars.CONFLUENCE_SPACE_KEY }}" \
      --parent-id "${{ vars.CONFLUENCE_PARENT_PAGE_ID }}" \
      --git-ref "${{ github.ref_name }}"
  env:
    CONFLUENCE_URL: ${{ secrets.CONFLUENCE_URL }}
    CONFLUENCE_EMAIL: ${{ secrets.CONFLUENCE_EMAIL }}
    CONFLUENCE_API_TOKEN: ${{ secrets.CONFLUENCE_API_TOKEN }}
```

Required GitHub repository secrets (`Settings → Secrets and variables → Actions`):

| Secret                 | Value                            |
| ---------------------- | -------------------------------- |
| `CONFLUENCE_URL`       | `https://<tenant>.atlassian.net` |
| `CONFLUENCE_EMAIL`     | Atlassian account email          |
| `CONFLUENCE_API_TOKEN` | API token from id.atlassian.com  |

Required GitHub repository variables (same settings page, `Variables` tab):

| Variable                    | Value                                      |
| --------------------------- | ------------------------------------------ |
| `CONFLUENCE_SPACE_KEY`      | Target space key (e.g. `DOCS`)             |
| `CONFLUENCE_PARENT_PAGE_ID` | Numeric ID of the pre-existing parent page |

## License

This package is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
