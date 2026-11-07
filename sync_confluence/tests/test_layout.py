"""Import-layering guard for the ``sync_confluence`` package layout.

Parses every source file with :mod:`ast` (no imports executed) and checks the
allowed-import table: ``confluence.storage_format`` < ``confluence`` <
``confluence.sync_cli`` < front ends (``markdown``, ``testspec``).
"""

from __future__ import annotations

import ast
import importlib
import pkgutil
import warnings
from pathlib import Path
from typing import Iterator

import pytest

import sync_confluence

_SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
_PKG = "sync_confluence"
_SHIMS = ("cli", "converter", "traversal")
_TWO_PART_SUBPACKAGES = {
    "confluence": ("storage_format", "sync_cli"),
    "markdown": ("converter", "traversal", "cli"),
}
_STORAGE_FORMAT = f"{_PKG}.confluence.storage_format"
_SYNC_CLI = f"{_PKG}.confluence.sync_cli"
_MARKDOWN = f"{_PKG}.markdown"
_TESTSPEC = f"{_PKG}.testspec"


def _is_under(module: str, prefix: str) -> bool:
    return module == prefix or module.startswith(f"{prefix}.")


def _module_name(source_file: Path) -> tuple[str, bool]:
    """Return ``(dotted module name, is_package_init)`` for *source_file*."""
    parts = list(source_file.relative_to(_SRC_ROOT).with_suffix("").parts)
    is_init = parts[-1] == "__init__"
    if is_init:
        parts.pop()
    return ".".join(parts), is_init


def _resolve_relative(
    module_name: str, is_init: bool, level: int, target: str | None
) -> str:
    package_parts = module_name.split(".")
    if not is_init:
        package_parts = package_parts[:-1]
    base_parts = package_parts[: len(package_parts) - (level - 1)]
    return ".".join([*base_parts, target] if target else base_parts)


def _imported_modules(source_file: Path) -> Iterator[str]:
    """Yield every ``sync_confluence`` module imported by *source_file*."""
    module_name, is_init = _module_name(source_file)
    tree = ast.parse(source_file.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name
        elif isinstance(node, ast.ImportFrom):
            base = (
                _resolve_relative(module_name, is_init, node.level, node.module)
                if node.level
                else node.module or ""
            )
            yield base
            for alias in node.names:
                yield f"{base}.{alias.name}"


def _subpackage(module: str) -> str:
    """Return the subpackage key (``confluence.sync_cli``, ``testspec``...)."""
    parts = module.split(".")[1:]
    if not parts:
        return ""
    if len(parts) > 1 and parts[1] in _TWO_PART_SUBPACKAGES.get(parts[0], ()):
        return ".".join(parts[:2])
    return parts[0]


def _private_cross_import(own_module: str, imported: str) -> bool:
    own, other = _subpackage(own_module), _subpackage(imported)
    if not own or own == other:
        return False
    remainder = imported.split(".")[1:]
    after_subpackage = remainder[len(other.split(".")) :]
    return any(segment.startswith("_") for segment in after_subpackage)


def _forbidden_reason(own_module: str, imported: str) -> str | None:
    """Return why *own_module* may not import *imported*, or ``None``."""
    if not _is_under(imported, _PKG):
        return None
    own = _subpackage(own_module)
    if _is_under(own_module, _STORAGE_FORMAT) and not _is_under(
        imported, _STORAGE_FORMAT
    ):
        return "confluence.storage_format may only import stdlib and lxml"
    if _is_under(own_module, f"{_PKG}.confluence") and not _is_under(
        own_module, _SYNC_CLI
    ):
        for upper in (_SYNC_CLI, _MARKDOWN, _TESTSPEC):
            if _is_under(imported, upper):
                return "confluence API modules must not import higher layers"
    if _is_under(own_module, _SYNC_CLI):
        for upper in (_MARKDOWN, _TESTSPEC):
            if _is_under(imported, upper):
                return "confluence.sync_cli must not import front ends"
    if _is_under(own_module, _MARKDOWN) and _is_under(imported, _TESTSPEC):
        return "markdown front end must not import testspec"
    if _is_under(own_module, _TESTSPEC) and _is_under(imported, _MARKDOWN):
        return "testspec front end must not import markdown"
    if own not in _SHIMS and any(
        _is_under(imported, f"{_PKG}.{shim}") for shim in _SHIMS
    ):
        return "deprecated shim import path (use sync_confluence.markdown.*)"
    if _private_cross_import(own_module, imported):
        return "private module of another subpackage (use its package-level name)"
    return None


def _violations_for(own_module: str, imports: list[str], label: str) -> list[str]:
    violations = []
    for imported in imports:
        reason = _forbidden_reason(own_module, imported)
        if reason:
            violations.append(
                f"Layering violation: {label} imports {imported} ({reason})"
            )
    return violations


def _source_files() -> list[Path]:
    return sorted((_SRC_ROOT / _PKG).rglob("*.py"))


def test_source_tree_has_no_layering_violations() -> None:
    violations = []
    for source_file in _source_files():
        module_name, _ = _module_name(source_file)
        violations.extend(
            _violations_for(
                module_name,
                sorted(set(_imported_modules(source_file))),
                str(source_file.relative_to(_SRC_ROOT)),
            )
        )

    assert not violations, "\n".join(violations)


@pytest.mark.parametrize("shim", _SHIMS)
def test_deprecated_shim_package_contains_only_init(shim: str) -> None:
    shim_dir = _SRC_ROOT / _PKG / shim

    assert sorted(path.name for path in shim_dir.glob("*.py")) == ["__init__.py"]


def _all_module_names() -> list[str]:
    """Every module in the package; ``__main__`` modules are skipped (they run)."""
    # walk_packages imports each package to recurse, which triggers the shims'
    # DeprecationWarning at collection time.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        return sorted(
            module_info.name
            for module_info in pkgutil.walk_packages(
                sync_confluence.__path__, prefix=f"{_PKG}."
            )
            if not module_info.name.endswith(".__main__")
        )


@pytest.mark.parametrize("module_name", _all_module_names())
def test_every_module_is_importable(module_name: str) -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        module = importlib.import_module(module_name)

    assert module.__name__ == module_name


@pytest.mark.parametrize(
    ("own_module", "imported", "fragment"),
    [
        (
            "sync_confluence.testspec._sync",
            "sync_confluence.confluence._lookup",
            "private module of another subpackage",
        ),
        (
            "sync_confluence.confluence._types",
            "sync_confluence.markdown.converter",
            "must not import higher layers",
        ),
        (
            "sync_confluence.confluence.storage_format._csf_document",
            "sync_confluence.confluence._constants",
            "only import stdlib and lxml",
        ),
        (
            "sync_confluence.confluence.sync_cli._finalise_sync_run",
            "sync_confluence.testspec",
            "must not import front ends",
        ),
        (
            "sync_confluence.markdown.cli._main",
            "sync_confluence.testspec._cli",
            "must not import testspec",
        ),
        (
            "sync_confluence.markdown.cli._main",
            "sync_confluence.converter",
            "deprecated shim",
        ),
    ],
)
def test_guard_flags_known_bad_imports(
    own_module: str, imported: str, fragment: str
) -> None:
    violations = _violations_for(own_module, [imported], own_module)

    assert violations
    assert violations[0].startswith("Layering violation:")
    assert fragment in violations[0]


def test_guard_allows_package_level_cross_imports() -> None:
    allowed = [
        "sync_confluence.confluence",
        "sync_confluence.confluence.storage_format",
        "sync_confluence.confluence.sync_cli",
    ]

    assert not _violations_for("sync_confluence.testspec._sync", allowed, "x")


def test_relative_imports_are_resolved() -> None:
    assert (
        _resolve_relative("sync_confluence.testspec._cli", False, 1, "_args")
        == "sync_confluence.testspec._args"
    )
    assert (
        _resolve_relative("sync_confluence.testspec", True, 1, "_args")
        == "sync_confluence.testspec._args"
    )
    assert (
        _resolve_relative("sync_confluence.testspec._cli", False, 2, None)
        == "sync_confluence"
    )
