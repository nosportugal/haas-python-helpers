from __future__ import annotations

import contextlib
import hashlib
import logging
from dataclasses import dataclass
from typing import Optional

from atlassian import Confluence

log = logging.getLogger(__name__)

# Confluence API response field keys
_KEY_ID = "id"
_KEY_VERSION = "version"
_KEY_NUMBER = "number"
_KEY_STORAGE = "storage"
_KEY_VALUE = "value"
_KEY_TITLE = "title"
_KEY_RESULTS = "results"

# Action values returned by upsert operations
_ACTION_CREATED = "created"
_ACTION_UPDATED = "updated"
_ACTION_UNCHANGED = "unchanged"
_ACTION_SKIPPED = "skipped"

_DRY_RUN_ID = "DRY-RUN"


@dataclass
class PageUpsertRequest:
    """Arguments for :func:`upsert_page`."""

    space_key: str
    parent_id: str
    title: str
    body: str
    dry_run: bool = False
    managed_by_label: Optional[str] = None
    restrict_edits_to: Optional[str] = None
    source_path: Optional[str] = None
    source_path_map: Optional[dict[str, str]] = None


@dataclass
class FolderUpsertRequest:
    """Arguments for :func:`upsert_folder`."""

    space_key: str
    parent_id: str
    title: str
    dry_run: bool = False
    managed_by_label: Optional[str] = None
    source_path: Optional[str] = None


@dataclass
class DeleteOrphansRequest:
    """Arguments for :func:`delete_orphans`."""

    root_page_id: str
    expected_titles: set[str]
    dry_run: bool = False
    managed_by_label: Optional[str] = None
    expected_paths: Optional[set[str]] = None


class _ConfluenceNotFoundFilter(logging.Filter):
    """Filter out 'Can\'t find' messages from the atlassian library."""

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: WPS125
        return "Can't find" not in record.getMessage()


@contextlib.contextmanager
def _suppress_atlassian_not_found():
    """Silence the atlassian-python-api ERROR logged when a title lookup returns
    no results.  'Not found' is an expected outcome during upsert; real errors
    surface through exceptions, not through that log message."""
    atlassian_logger = logging.getLogger("atlassian.confluence")
    log_filter = _ConfluenceNotFoundFilter()
    atlassian_logger.addFilter(log_filter)
    try:
        yield
    finally:
        atlassian_logger.removeFilter(log_filter)


def _request_edit_restriction(
    confluence: Confluence, page_id: str, account_id: str
) -> None:
    """Execute the PUT to set edit restrictions; raises on HTTP error."""
    api_response = confluence.request(
        method="PUT",
        path=f"rest/api/content/{page_id}/restriction/byOperation/update/user",
        params={"accountId": account_id},
        advanced_mode=True,
    )
    api_response.raise_for_status()
    log.debug("Set edit restriction on page id=%s to accountId=%s", page_id, account_id)


def _apply_edit_restriction(
    confluence: Confluence, page_id: str, account_id: str
) -> None:
    """Restrict edit access on the page to the given Atlassian accountId."""
    try:
        _request_edit_restriction(confluence, page_id, account_id)
    except Exception as exc:
        log.warning(
            "Could not set edit restriction on page id=%s: %s",
            page_id,
            exc,
        )


def _find_page_under_parent(
    confluence: Confluence,
    space_key: str,
    title: str,
    parent_id: str,
) -> Optional[dict]:
    """Find a page by title, verifying it's under the expected parent.

    Returns ``{"id": str, "version": int, "body": str}`` or ``None``.
    """
    with _suppress_atlassian_not_found():
        page = confluence.get_page_by_title(
            space=space_key,
            title=title,
            expand="version,body.storage,ancestors",
        )
    if not page:
        return None

    # Verify immediate parent to avoid title collisions
    ancestors = page.get("ancestors", [])
    if not ancestors:
        return None
    if str(ancestors[-1][_KEY_ID]) != str(parent_id):
        return None

    return {
        _KEY_ID: str(page[_KEY_ID]),
        "version": page[_KEY_VERSION][_KEY_NUMBER],
        "body": page.get("body", {}).get(_KEY_STORAGE, {}).get(_KEY_VALUE, ""),
    }


def _fetch_child_folder(
    confluence: Confluence, parent_id: str, title: str
) -> Optional[dict]:
    """Return folder info via the child/folder endpoint, or ``None`` if not found."""
    response = (
        confluence.get(
            path=f"rest/api/content/{parent_id}/child/folder",
            params={"limit": 200, "expand": _KEY_VERSION},
        )
        or {}
    )
    for folder_entry in response.get(_KEY_RESULTS, []):
        if folder_entry.get(_KEY_TITLE) == title:
            return {
                _KEY_ID: str(folder_entry[_KEY_ID]),
                _KEY_VERSION: folder_entry[_KEY_VERSION][_KEY_NUMBER],
            }
    return None


def _cql_folder_by_parent(
    confluence: Confluence, space_key: str, title: str, parent_id: str
) -> Optional[dict]:
    """Search for a folder by CQL scoped to parent; returns folder info or ``None``."""
    cql = (
        f'type=folder AND space.key="{space_key}" '
        f'AND title="{title}" AND parent={parent_id}'
    )
    cql_results = confluence.cql(cql, limit=5) or {}
    for search_entry in cql_results.get(_KEY_RESULTS, []):
        folder_data = search_entry.get("content", search_entry)
        if folder_data.get(_KEY_TITLE) == title:
            return {_KEY_ID: str(folder_data[_KEY_ID]), _KEY_VERSION: 1}
    return None


def _find_folder_by_space_cql(
    confluence: Confluence, space_key: str, title: str
) -> Optional[str]:
    """Search for a folder space-wide by CQL; returns folder_id or ``None``."""
    cql = f'type=folder AND space.key="{space_key}" AND title="{title}"'
    cql_results = confluence.cql(cql, limit=5) or {}
    for search_entry in cql_results.get(_KEY_RESULTS, []):
        folder_data = search_entry.get("content", search_entry)
        if folder_data.get(_KEY_TITLE) == title:
            return str(folder_data[_KEY_ID])
    return None


def _find_folder_under_parent(
    confluence: Confluence,
    space_key: str,
    title: str,
    parent_id: str,
) -> Optional[dict]:
    """Find a Confluence Folder by title under *parent_id*.

    Uses the child-folder endpoint (``/rest/api/content/{id}/child/folder``)
    first; falls back to a CQL search when that endpoint fails or returns
    no results, because Confluence Cloud may not expose the endpoint for all
    content types.

    Returns ``{"id": str, "version": int}`` or ``None``.
    """
    # Primary: dedicated child/folder endpoint
    folder: Optional[dict] = None
    try:
        folder = _fetch_child_folder(confluence, parent_id, title)
    except Exception as exc:
        log.debug(
            "child/folder endpoint failed for parent %s (%s); trying CQL fallback",
            parent_id,
            exc,
        )

    if folder:
        return folder

    # Fallback: CQL search scoped to the space and parent
    try:
        folder = _cql_folder_by_parent(confluence, space_key, title, parent_id)
    except Exception as exc:
        log.debug("CQL folder search failed for '%s': %s", title, exc)

    return folder


def _content_hash(body: str) -> str:
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _fetch_hash_prop_value(confluence: Confluence, page_id: str) -> Optional[str]:
    """Return the stored content hash for *page_id*, or ``None`` if absent."""
    prop = confluence.get_page_property(page_id, _HASH_PROPERTY_KEY)
    return prop[_KEY_VALUE] if prop and _KEY_VALUE in prop else None


# Property key for storing the hash of the generated body
_HASH_PROPERTY_KEY = "sync_confluence_hash"
# Property key for storing the docs-root-relative source file path
_SOURCE_PATH_PROPERTY_KEY = "sync_confluence_source_path"


def _upsert_page_property(
    confluence: Confluence, page_id: str, key: str, prop_value: str
) -> None:
    """Create or update a page property, handling versioning for updates."""
    try:
        prop = confluence.get_page_property(page_id, key)
    except Exception:
        prop = None  # Property does not exist yet \u2014 will be created below

    if prop and _KEY_VERSION in prop:
        version = prop.get(_KEY_VERSION, {}).get(_KEY_NUMBER, 1)
        response = confluence.request(
            method="PUT",
            path=f"rest/api/content/{page_id}/property/{key}",
            data={
                "key": key,
                _KEY_VALUE: prop_value,
                "version": {"number": version + 1},
            },
            advanced_mode=True,
        )
    else:
        response = confluence.request(
            method="POST",
            path=f"rest/api/content/{page_id}/property",
            data={"key": key, _KEY_VALUE: prop_value},
            advanced_mode=True,
        )
    response.raise_for_status()


def _get_child_folders(confluence: Confluence, parent_id: str) -> list[dict]:
    """Return the direct child Confluence Folders under *parent_id*.

    Paginates until all results are fetched.
    """
    child_results: list[dict] = []
    limit = 200
    start = 0
    while True:
        try:
            response = (
                confluence.get(
                    path=f"rest/api/content/{parent_id}/child/folder",
                    params={"limit": limit, "start": start},
                )
                or {}
            )
        except Exception:
            break
        page = response.get(_KEY_RESULTS, [])
        child_results.extend(page)
        if len(page) < limit:
            break
        start += limit
    return child_results


def _apply_label(confluence: Confluence, page_id: str, label: str) -> None:
    """Attach *label* to *page_id*; idempotent."""
    confluence.set_page_label(page_id, label)


def _page_has_label(confluence: Confluence, page_id: str, label: str) -> bool:
    """Return ``True`` if *page_id* carries *label*.

    Uses a direct REST call so that both page and folder content types are
    handled correctly.
    """
    page_labels: dict = {}
    try:
        page_labels = confluence.get(path=f"rest/api/content/{page_id}/label") or {}
    except Exception:
        return False
    entries = page_labels.get(_KEY_RESULTS, [])
    return any(entry["name"] == label for entry in entries)


def _get_source_path_property(confluence: Confluence, page_id: str) -> Optional[str]:
    """Fetch the ``sync_confluence_source_path`` property, or ``None`` if absent."""
    try:
        prop = confluence.get_page_property(page_id, _SOURCE_PATH_PROPERTY_KEY)
    except Exception as exc:
        log.debug(
            "Failed to fetch page property '%s' for page id=%s: %s",
            _SOURCE_PATH_PROPERTY_KEY,
            page_id,
            exc,
        )
        return None
    return prop[_KEY_VALUE] if prop and _KEY_VALUE in prop else None


def _fetch_child_page_batch(
    confluence: Confluence, parent_id: str, limit: int, start: int
) -> Optional[dict]:
    """Fetch one batch of child pages; returns ``None`` on error."""
    try:
        return (
            confluence.get(
                path=f"rest/api/content/{parent_id}/child/page",
                params={"limit": limit, "start": start},
            )
            or {}
        )
    except Exception as exc:
        log.debug(
            "Could not fetch child pages for parent %s to build source path map: %s",
            parent_id,
            exc,
        )
        return None


def _register_source_path(
    path_map: dict[str, str], source_path: str, page_id: str
) -> None:
    """Add ``source_path → page_id`` to *path_map*, warning on duplicates."""
    if source_path in path_map:
        log.warning(
            "Duplicate source_path '%s' on pages id=%s and id=%s; "
            "keeping id=%s for rename detection",
            source_path,
            path_map.get(source_path),
            page_id,
            path_map.get(source_path),
        )
        return
    path_map[source_path] = page_id


def _ingest_page_batch(
    confluence: Confluence, pages: list[dict], path_map: dict[str, str]
) -> None:
    """For each page, look up its source_path property and register it."""
    for page in pages:
        page_id = str(page[_KEY_ID])
        source_path = _get_source_path_property(confluence, page_id)
        if source_path:
            _register_source_path(path_map, source_path, page_id)


def build_source_path_map(
    confluence: Confluence,
    parent_id: str,
) -> dict[str, str]:
    """Return a ``{source_path: page_id}`` mapping for all managed child pages
    under *parent_id* that have the ``sync_confluence_source_path`` property set.

    Used for rename detection: when a file's source path is in the mapping
    under a different title, the existing page is updated in-place instead of
    creating a duplicate.  Pages without the property are silently skipped.
    Paginates through all children (up to 200 per request).
    """
    path_map: dict[str, str] = {}
    limit = 200
    start = 0
    while True:
        response = _fetch_child_page_batch(confluence, parent_id, limit, start)
        if response is None:
            break
        pages = response.get(_KEY_RESULTS, [])
        _ingest_page_batch(confluence, pages, path_map)
        if len(pages) < limit:
            break
        start += limit
    return path_map


def _try_property_set(
    confluence: Confluence, page_id: str, key: str, prop_value: str, what: str
) -> None:
    """Best-effort property set, logging failures without raising."""
    try:
        _upsert_page_property(confluence, page_id, key, prop_value)
    except Exception as exc:
        log.warning("Could not set %s property for page id=%s: %s", what, page_id, exc)


def _apply_page_metadata(
    confluence: Confluence,
    page_id: str,
    request: PageUpsertRequest,
    body_hash: str,
) -> None:
    """Apply hash + source-path properties, label and edit restriction to a page."""
    _try_property_set(confluence, page_id, _HASH_PROPERTY_KEY, body_hash, "hash")
    if request.source_path is not None:
        _try_property_set(
            confluence,
            page_id,
            _SOURCE_PATH_PROPERTY_KEY,
            request.source_path,
            "source path",
        )
    if request.managed_by_label:
        _apply_label(confluence, page_id, request.managed_by_label)
    if request.restrict_edits_to:
        _apply_edit_restriction(confluence, page_id, request.restrict_edits_to)


def _log_dry_run_metadata(request: PageUpsertRequest) -> None:
    """Emit the optional [DRY-RUN] label/restriction debug lines."""
    if request.managed_by_label:
        log.debug(
            "[DRY-RUN] Would label '%s' with '%s'",
            request.title,
            request.managed_by_label,
        )
    if request.restrict_edits_to:
        log.debug(
            "[DRY-RUN] Would restrict edits on '%s' to accountId=%s",
            request.title,
            request.restrict_edits_to,
        )


def _rename_target(request: PageUpsertRequest) -> Optional[str]:
    """Return the page id to rename, if a rename should occur."""
    if request.source_path is None or not request.source_path_map:
        return None
    return request.source_path_map.get(request.source_path)


def _upsert_page_dry_run(
    confluence: Confluence, request: PageUpsertRequest
) -> tuple[str, str]:
    """Simulate :func:`upsert_page` for dry-run mode."""
    existing = _find_page_under_parent(
        confluence, request.space_key, request.title, request.parent_id
    )
    rename_id = None if existing else _rename_target(request)
    if rename_id is not None:
        log.info(
            "[DRY-RUN] Would rename page id=%s to '%s' and update content",
            rename_id,
            request.title,
        )
        _log_dry_run_metadata(request)
        return (_DRY_RUN_ID, _ACTION_UPDATED)
    _log_dry_run_metadata(request)
    return (_DRY_RUN_ID, _ACTION_CREATED)


def _handle_page_rename(
    confluence: Confluence, request: PageUpsertRequest
) -> Optional[tuple[str, str]]:
    """If a rename target exists, update its body+metadata and return result."""
    rename_id = _rename_target(request)
    if rename_id is None:
        return None
    log.info(
        "Renaming page id=%s to '%s' and updating content",
        rename_id,
        request.title,
    )
    confluence.update_page(
        page_id=rename_id,
        title=request.title,
        body=request.body,
        parent_id=request.parent_id,
        representation=_KEY_STORAGE,
        minor_edit=True,
    )
    _apply_page_metadata(confluence, rename_id, request, _content_hash(request.body))
    return (rename_id, _ACTION_UPDATED)


def _check_title_collision(
    confluence: Confluence, request: PageUpsertRequest
) -> Optional[tuple[None, str]]:
    """Return SKIPPED result if a same-titled page exists under a different parent."""
    with _suppress_atlassian_not_found():
        conflicting_page = confluence.get_page_by_title(
            space=request.space_key,
            title=request.title,
            expand=_KEY_VERSION,
        )
    if not conflicting_page:
        log.debug(
            "'%s' not found in space, will create under parent %s",
            request.title,
            request.parent_id,
        )
        return None
    log.warning(
        "Title collision: '%s' already exists in space (id=%s) under a "
        "different parent — skipping this file to avoid hijacking an "
        "unrelated page.",
        request.title,
        conflicting_page[_KEY_ID],
    )
    return (None, _ACTION_SKIPPED)


def _update_existing_page(
    confluence: Confluence, request: PageUpsertRequest, existing_id: str
) -> tuple[str, str]:
    """Hash-check then update an existing page; returns ``(id, action)``."""
    body_hash = _content_hash(request.body)
    prop_val = None
    try:
        prop_val = _fetch_hash_prop_value(confluence, existing_id)
    except Exception as exc:
        log.warning(
            "Could not fetch hash property for page id=%s (%s); will update",
            existing_id,
            exc,
        )

    if prop_val == body_hash:
        log.debug("Unchanged: '%s' (id=%s)", request.title, existing_id)
        return (existing_id, _ACTION_UNCHANGED)

    confluence.update_page(
        page_id=existing_id,
        title=request.title,
        body=request.body,
        parent_id=request.parent_id,
        representation=_KEY_STORAGE,
        minor_edit=True,
    )
    log.info("Updated: '%s' (id=%s)", request.title, existing_id)
    _apply_page_metadata(confluence, existing_id, request, body_hash)
    return (existing_id, _ACTION_UPDATED)


def _create_new_page(
    confluence: Confluence, request: PageUpsertRequest
) -> tuple[str, str]:
    """Create a new page and apply metadata."""
    page = confluence.create_page(
        space=request.space_key,
        title=request.title,
        body=request.body,
        parent_id=request.parent_id,
        representation=_KEY_STORAGE,
    )
    page_id = str(page[_KEY_ID])
    log.info("Created: '%s' (id=%s)", request.title, page_id)
    _apply_page_metadata(confluence, page_id, request, _content_hash(request.body))
    return (page_id, _ACTION_CREATED)


def upsert_page(
    confluence: Confluence, request: PageUpsertRequest
) -> tuple[Optional[str], str]:
    """Create or update a page.  Returns ``(page_id, action)``.

    *action* is one of ``"created"``, ``"updated"``, ``"unchanged"``, or
    ``"skipped"``.  When *action* is ``"skipped"``, *page_id* is ``None``
    and the page was not touched.  This happens when a page with the same
    title already exists in the space under a **different** parent: hijacking
    and re-parenting that page is forbidden, so the caller is expected to log
    the collision and exclude the file from its results.
    In dry-run mode, *page_id* is ``"DRY-RUN"``.

    When ``request.managed_by_label`` is set, the label is applied to every
    created or updated page so that :func:`delete_orphans` can safely restrict
    deletions to only pages owned by this automation.

    When ``request.restrict_edits_to`` is set (an Atlassian ``accountId``),
    the page's ``update`` restriction is set to allow only that account to
    edit.  View access is left unrestricted.  The restriction is applied on
    create and update; unchanged pages are skipped to avoid unnecessary API
    calls.
    """
    if request.dry_run:
        return _upsert_page_dry_run(confluence, request)
    existing = _find_page_under_parent(
        confluence, request.space_key, request.title, request.parent_id
    )
    if existing is not None:
        return _update_existing_page(confluence, request, existing[_KEY_ID])
    renamed = _handle_page_rename(confluence, request)
    if renamed is not None:
        return renamed
    collision = _check_title_collision(confluence, request)
    if collision is not None:
        return collision
    return _create_new_page(confluence, request)


def _upsert_folder_dry_run(request: FolderUpsertRequest) -> tuple[str, str]:
    if request.managed_by_label:
        log.debug(
            "[DRY-RUN] Would label folder '%s' with '%s'",
            request.title,
            request.managed_by_label,
        )
    return (_DRY_RUN_ID, _ACTION_CREATED)


def _refresh_existing_folder(
    confluence: Confluence, request: FolderUpsertRequest, existing_id: str
) -> tuple[str, str]:
    log.debug("Unchanged folder: '%s' (id=%s)", request.title, existing_id)
    # Re-apply label so it is self-healing if it was ever missing.
    if request.managed_by_label:
        _apply_label(confluence, existing_id, request.managed_by_label)
    if request.source_path is not None:
        _try_property_set(
            confluence,
            existing_id,
            _SOURCE_PATH_PROPERTY_KEY,
            request.source_path,
            "source path",
        )
    return (existing_id, _ACTION_UNCHANGED)


def _post_create_folder_setup(
    confluence: Confluence, folder_id: str, request: FolderUpsertRequest
) -> None:
    if request.managed_by_label:
        _apply_label(confluence, folder_id, request.managed_by_label)
    if request.source_path is not None:
        _try_property_set(
            confluence,
            folder_id,
            _SOURCE_PATH_PROPERTY_KEY,
            request.source_path,
            "source path",
        )


def _create_folder_via_api(confluence: Confluence, request: FolderUpsertRequest) -> str:
    folder_item = confluence.post(
        path="rest/api/content",
        data={
            "type": "folder",
            "title": request.title,
            "space": {"key": request.space_key},
            "ancestors": [{_KEY_ID: request.parent_id}],
        },
    )
    return str(folder_item[_KEY_ID])


def _is_folder_exists_error(exc) -> bool:
    """Return True if *exc* indicates a folder-already-exists conflict."""
    has_response = exc.response is not None
    return "folder exists" in str(exc).lower() or (
        has_response and exc.response.status_code in (400, 409)
    )


def _lookup_existing_folder_via_cql(
    confluence: Confluence, request: FolderUpsertRequest
) -> Optional[str]:
    try:
        return _find_folder_by_space_cql(confluence, request.space_key, request.title)
    except Exception as cql_exc:
        log.debug("CQL fallback also failed: %s", cql_exc)
        return None


def _create_folder_with_fallback(
    confluence: Confluence, request: FolderUpsertRequest
) -> tuple[str, str]:
    from requests.exceptions import HTTPError

    try:
        folder_id = _create_folder_via_api(confluence, request)
    except HTTPError as exc:
        # Confluence Cloud rejects the create if a folder with this title
        # already exists anywhere in the space, even when our child-folder
        # lookup didn't find it (endpoint unreliable for some tenants).
        # Attempt a second, broader lookup before giving up.
        if not _is_folder_exists_error(exc):
            raise
        log.debug(
            "Folder '%s' creation rejected (%s); attempting broader lookup",
            request.title,
            exc,
        )
        fallback_id = _lookup_existing_folder_via_cql(confluence, request)
        if fallback_id:
            log.info(
                "Found existing folder '%s' via CQL (id=%s)",
                request.title,
                fallback_id,
            )
            return (fallback_id, _ACTION_UNCHANGED)
        raise
    log.info("Created folder: '%s' (id=%s)", request.title, folder_id)
    _post_create_folder_setup(confluence, folder_id, request)
    return (folder_id, _ACTION_CREATED)


def upsert_folder(
    confluence: Confluence, request: FolderUpsertRequest
) -> tuple[str, str]:
    """Create or find a Confluence Folder.  Returns ``(folder_id, action)``.

    *action* is one of ``"created"`` or ``"unchanged"``.
    In dry-run mode, *folder_id* is ``"DRY-RUN"``.

    Folders have no editable body content, so no edit restriction is applied.
    The ``request.managed_by_label`` is attached on creation so that
    ``delete_orphans`` can identify and clean up stale folders.
    """
    if request.dry_run:
        return _upsert_folder_dry_run(request)
    existing = _find_folder_under_parent(
        confluence, request.space_key, request.title, request.parent_id
    )
    if existing:
        return _refresh_existing_folder(confluence, request, existing[_KEY_ID])
    return _create_folder_with_fallback(confluence, request)


def _list_immediate_children(confluence: Confluence, page_id: str) -> list[dict]:
    """Return pages + folders immediately under *page_id* (best effort)."""
    try:
        pages = confluence.get_child_pages(page_id) or []
    except Exception:
        pages = []
    folders = _get_child_folders(confluence, page_id)
    return list(pages) + list(folders)


def _collect_children(confluence: Confluence, page_id: str) -> list[dict]:
    """Recursively collect all descendant pages and folders under *page_id*.

    Returns a flat list of ``{"id", "title"}`` dicts ordered leaves-first
    (safe for bottom-up deletion).  Both pages and Confluence Folder objects
    are included so that orphan cleanup can remove stale folders.
    """
    collection: list[dict] = []
    for child in _list_immediate_children(confluence, page_id):
        child_id = str(child[_KEY_ID])
        # Append grandchildren first (depth-first / leaves-first)
        collection.extend(_collect_children(confluence, child_id))
        collection.append({_KEY_ID: child_id, _KEY_TITLE: child[_KEY_TITLE]})
    return collection


def _is_kept_by_path(
    confluence: Confluence, orphan_id: str, expected_paths: Optional[set[str]]
) -> Optional[str]:
    """Return source_path string if the page should be kept, else None."""
    if expected_paths is None:
        return None
    source_path = _get_source_path_property(confluence, orphan_id)
    if source_path is None or source_path not in expected_paths:
        return None
    return source_path


def _is_orphan_eligible(
    confluence: Confluence, page: dict, request: DeleteOrphansRequest
) -> bool:
    """True if *page* is an orphan and the caller should delete it."""
    orphan_title = page[_KEY_TITLE]
    orphan_id = page[_KEY_ID]
    if orphan_title in request.expected_titles:
        return False
    kept_path = _is_kept_by_path(confluence, orphan_id, request.expected_paths)
    if kept_path is not None:
        log.debug(
            "Keeping '%s' (id=%s) — source path '%s' still exists",
            orphan_title,
            orphan_id,
            kept_path,
        )
        return False
    if request.managed_by_label and not _page_has_label(
        confluence, orphan_id, request.managed_by_label
    ):
        log.debug("Skipping non-managed page: '%s' (id=%s)", orphan_title, orphan_id)
        return False
    return True


def _delete_one_orphan(
    confluence: Confluence, orphan_id: str, orphan_title: str, dry_run: bool
) -> None:
    if dry_run:
        log.info("[DRY-RUN] Would delete orphan: '%s' (id=%s)", orphan_title, orphan_id)
        return
    confluence.remove_page(orphan_id)
    log.info("Deleted orphan: '%s' (id=%s)", orphan_title, orphan_id)


def delete_orphans(confluence: Confluence, request: DeleteOrphansRequest) -> int:
    """Delete pages under ``request.root_page_id`` whose titles are not in
    ``request.expected_titles`` and whose source paths are not in
    ``request.expected_paths``.

    Deletes bottom-up to avoid cascade issues.  Returns the count of deleted
    pages.

    When ``request.managed_by_label`` is set, only pages that carry that label
    are eligible for deletion.  Pages created outside this automation are
    left untouched even if their title is not in *expected_titles*.

    When ``request.expected_paths`` is set, each candidate's
    ``sync_confluence_source_path`` page property is checked before deletion.
    A page whose stored source path is still in *expected_paths* is kept even
    if its title changed (rename detection).  Pages that pre-date this feature
    and carry no source path property fall back to title-matching only.
    """
    all_pages = _collect_children(confluence, request.root_page_id)
    deleted = 0
    for page in all_pages:
        if not _is_orphan_eligible(confluence, page, request):
            continue
        _delete_one_orphan(confluence, page[_KEY_ID], page[_KEY_TITLE], request.dry_run)
        deleted += 1
    return deleted
