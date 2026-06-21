# Phase 2 — Replace `--mermaid-macro` with a YAML configuration file

## Goal

Remove the `--mermaid-macro` CLI argument (and its `CONFLUENCE_MERMAID_MACRO` environment variable counterpart) and replace them with a **per-repository YAML configuration file** (`.sync-confluence.yml`).

This decouples diagram macro configuration from the command line, allows multiple diagram backends to be configured in one place, and lays the groundwork for other future per-repo settings.

---

## Proposed configuration file

**Filename:** `.sync-confluence.yml` (auto-discovered; location described below)

```yaml
diagrams:
  mermaid:
    macro: "diagram"        # Confluence macro key for Mermaid blocks
  plantuml:
    macro: "plantuml"       # Confluence macro key for PlantUML blocks
```

### Discovery order

The tool looks for `.sync-confluence.yml` in the following locations, in order, and uses the first file found:

1. The directory passed to `--docs-dir` (or the auto-detected docs directory).
2. The repository root (the working directory where the CLI is invoked).

An explicit path can also be provided via a new `--config` CLI argument (see below).

### Schema

```
diagrams:               # optional section
  mermaid:              # optional subsection
    macro: <string>     # Confluence macro key (ac:name value)
  plantuml:             # optional subsection
    macro: <string>     # Confluence macro key
```

All keys are optional. An empty or absent file is valid and produces the same behaviour as today when no `--mermaid-macro` is passed (diagram blocks render as plain code blocks).

---

## Changes required

### 1. `pyproject.toml`

Add `pyyaml` as a runtime dependency:

```toml
dependencies = [
    "atlassian-python-api>=3.41.0",
    "markdown>=3.7",
    "pyyaml>=6.0",
]
```

### 2. `src/sync_confluence/cli/_env.py`

Add a `_load_config()` helper that discovers and parses the YAML file:

```python
import yaml
from pathlib import Path

_CONFIG_FILENAME = ".sync-confluence.yml"


def _load_config(docs_dir: Optional[Path] = None) -> dict:
    """Load .sync-confluence.yml from docs_dir or cwd, whichever is found first.

    Returns an empty dict when no file is found or the file is empty.
    """
    candidates = []
    if docs_dir:
        candidates.append(docs_dir / _CONFIG_FILENAME)
    candidates.append(Path.cwd() / _CONFIG_FILENAME)

    for path in candidates:
        if path.is_file():
            log.debug("Loading config from %s", path)
            with path.open() as fh:
                return yaml.safe_load(fh) or {}

    return {}


def _config_mermaid_macro(config: dict) -> Optional[str]:
    """Extract diagrams.mermaid.macro from a loaded config dict."""
    return config.get("diagrams", {}).get("mermaid", {}).get("macro")


def _config_plantuml_macro(config: dict) -> Optional[str]:
    """Extract diagrams.plantuml.macro from a loaded config dict."""
    return config.get("diagrams", {}).get("plantuml", {}).get("macro")
```

### 3. `src/sync_confluence/cli/_args.py`

- **Remove** the `--mermaid-macro` argument from `_add_sync_args()`.
- **Add** an optional `--config` argument:

```python
parser.add_argument(
    "--config",
    default=None,
    metavar="FILE",
    help=(
        "Path to a .sync-confluence.yml config file. "
        "Auto-discovered from --docs-dir or the working directory when not set."
    ),
)
```

Also **remove** the `CONFLUENCE_MERMAID_MACRO` env var lookup (the `_env("CONFLUENCE_MERMAID_MACRO")` default).

### 4. `src/sync_confluence/traversal/_state.py`

Add `plantuml_macro` to `SyncContext` alongside the existing `mermaid_macro`:

```python
@dataclass
class SyncContext:
    ...
    mermaid_macro: Optional[str] = None
    plantuml_macro: Optional[str] = None   # NEW
    ...
```

### 5. `src/sync_confluence/cli/_dispatch.py`

Load the config and pass both macro values when building `SyncContext`:

```python
from sync_confluence.cli._env import _load_config, _config_mermaid_macro, _config_plantuml_macro
from pathlib import Path

def _build_sync_context(
    args: argparse.Namespace, docs: _DocsInfo, auth: _AuthInfo
) -> SyncContext:
    config_path = Path(args.config) if args.config else None
    config = _load_config(config_path or docs.root)
    return SyncContext(
        confluence=auth.confluence,
        space_key=args.space,
        docs_root=docs.root,
        root_title=args.root_title,
        mermaid_macro=_config_mermaid_macro(config),
        plantuml_macro=_config_plantuml_macro(config),
        repo_url=auth.repo_url,
        git_ref=args.git_ref,
        dry_run=args.dry_run,
        managed_by_label=auth.managed_by_label,
        restrict_edits_to=auth.restrict_edits_to,
    )
```

### 6. `src/sync_confluence/converter.py`

Extend `convert_markdown()` (and `_replace_code_block()`) to accept and use `plantuml_macro`:

```python
def convert_markdown(
    text: str,
    *,
    mermaid_macro: Optional[str] = None,
    plantuml_macro: Optional[str] = None,   # NEW
    repo_url: Optional[str] = None,
    git_ref: str = "main",
    current_file: Optional[Path] = None,
) -> str:
    ...
```

In `_replace_code_block()`, add handling for `language == "plantuml"` analogous to the existing `mermaid` branch.

### 7. `README.md`

- Remove the `--mermaid-macro` / `CONFLUENCE_MERMAID_MACRO` documentation.
- Add a section documenting `.sync-confluence.yml` with the full schema and an example.
- Document the new `--config` argument.

### 8. `tests/test_cli.py`

- Remove tests that exercise `--mermaid-macro` / `CONFLUENCE_MERMAID_MACRO`.
- Add tests for `_load_config()`:
  - No file present → returns `{}`.
  - File in `docs_dir` takes priority over file in cwd.
  - Explicit `--config` path takes priority over auto-discovery.
  - Malformed YAML raises a clear error.
- Add tests for `_config_mermaid_macro()` and `_config_plantuml_macro()`.

---

## Migration / backward compatibility

| Scenario | Before (today) | After (Phase 2) |
|---|---|---|
| CI pipeline using `--mermaid-macro diagram` | Works | **Breaking** — must move to `.sync-confluence.yml` |
| CI pipeline using `CONFLUENCE_MERMAID_MACRO=diagram` | Works | **Breaking** — must move to `.sync-confluence.yml` |
| No diagram config (plain code block fallback) | Works | Works unchanged |

Because this is a breaking change for anyone using the mermaid flag, **ship a deprecation warning** in an intermediate release before removing the argument:

1. **Release N** — Add `.sync-confluence.yml` support; keep `--mermaid-macro` / `CONFLUENCE_MERMAID_MACRO` but emit a `DeprecationWarning` log line when they are used.
2. **Release N+1** — Remove `--mermaid-macro` / `CONFLUENCE_MERMAID_MACRO` entirely.

---

## Out of scope for Phase 2

- JSON Schema / strict validation of `.sync-confluence.yml` (nice-to-have, later).
- Other config keys beyond `diagrams` (e.g. label defaults, page restrictions).
- CLI-level override flags per diagram type (e.g. `--plantuml-macro`).
