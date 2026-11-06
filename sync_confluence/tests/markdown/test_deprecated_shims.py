"""Deprecated ``cli`` / ``converter`` / ``traversal`` shims and command alias."""

from __future__ import annotations

import importlib
import logging
import sys
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest

from sync_confluence.markdown.cli import deprecated_sync_confluence_main

_SHIM_ALL = (
    ("sync_confluence.cli", ["main", "parse_args", "validate_args"]),
    (
        "sync_confluence.converter",
        [
            "Attachment",
            "ConversionError",
            "ConversionResult",
            "ConverterOptions",
            "MermaidRenderer",
            "RenderedImage",
            "RepoContext",
            "SourcePaths",
            "convert_markdown",
            "derive_title",
        ],
    ),
    (
        "sync_confluence.traversal",
        [
            "SyncContext",
            "SyncResult",
            "build_doc_index",
            "sync_directory",
            "sync_files",
        ],
    ),
)
_ALIAS_WARNING = (
    "sync-confluence and python -m sync_confluence are deprecated; "
    "use sync-confluence-markdown"
)


def _fresh_import(module_name: str) -> ModuleType:
    sys.modules.pop(module_name, None)
    return importlib.import_module(module_name)


@pytest.mark.parametrize(("module_name", "old_all"), _SHIM_ALL)
def test_shim_warns_and_exposes_old_all(module_name: str, old_all: list[str]) -> None:
    with pytest.deprecated_call(match=f"{module_name} is deprecated"):
        shim = _fresh_import(module_name)

    assert sorted(shim.__all__) == sorted(old_all)
    for exported_name in old_all:
        assert hasattr(shim, exported_name)


def test_cli_shim_main_is_markdown_sync_main() -> None:
    with pytest.deprecated_call():
        shim = _fresh_import("sync_confluence.cli")

    from sync_confluence.markdown.cli import markdown_sync_main

    assert shim.main is markdown_sync_main


def test_deprecated_alias_logs_warning_and_delegates(
    caplog: pytest.LogCaptureFixture,
) -> None:
    target = "sync_confluence.markdown.cli._deprecated_alias.markdown_sync_main"
    with patch(target, new_callable=MagicMock) as mock_main:
        with caplog.at_level(logging.WARNING):
            deprecated_sync_confluence_main()

    assert _ALIAS_WARNING in caplog.text
    mock_main.assert_called_once_with()
