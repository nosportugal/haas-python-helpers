"""Shared bundle of (ctx, builder, recorder) passed to walker steps."""

from __future__ import annotations

from dataclasses import dataclass

from sync_confluence.traversal._builder import _RequestBuilder
from sync_confluence.traversal._state import SyncContext, _SyncRecorder

_DRY_RUN_ID = "DRY-RUN"
_LOG_INDENT = "  "


@dataclass
class _Sync:
    """Aggregates the immutable context, request builder and result recorder."""

    ctx: SyncContext
    builder: _RequestBuilder
    recorder: _SyncRecorder


def _new_state(ctx: SyncContext, *, allow_root_title: bool) -> _Sync:
    return _Sync(
        ctx=ctx,
        builder=_RequestBuilder(ctx, allow_root_title=allow_root_title),
        recorder=_SyncRecorder(ctx.docs_root),
    )


def _maybe_log(dry_run: bool, depth: int, icon: str, title: str) -> None:
    """Emit one dry-run preview line, if dry-run mode is active."""
    if dry_run:
        from sync_confluence.traversal._state import log

        log.info("%s%s %s", _LOG_INDENT * depth, icon, title)
