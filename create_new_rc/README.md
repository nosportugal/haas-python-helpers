# create-new-rc

Create a release candidate tag and PR for a GitHub repository.

## Features

- Automatic RC tag generation (e.g., `v2026.2.0-rc3`)
- Hotfix support (e.g., `v2026.2.0-h1-rc0`)
- Release branch creation
- PR automation
- Dry-run mode for previewing changes
- API-verified commits (no GPG signing required)

## Installation

Local development:

```bash
pip install -e create_new_rc/
```

In CI via git:

```bash
pip install git+https://github.com/nosportugal/haas-python-helpers.git#subdirectory=create_new_rc
```

## Requirements

- Python >= 3.11
- `gh` CLI tool (for GitHub API access)

## Usage

### Create a regular RC

```bash
create-rc
```

### Create a hotfix RC

```bash
create-rc --type hotfix --base-version v2026.2.0
```

### Dry-run mode

```bash
create-rc --dry-run
```

### Specify repository

```bash
create-rc --repo owner/repo
```

## Options

- `--type {regular,hotfix}` — RC type (default: `regular`)
- `--base-version VERSION` — Base version, e.g., `v2026.2.0`
- `--repo OWNER/REPO` — GitHub repository (defaults to current repo via `gh`)
- `--dry-run` — Preview without making API calls
