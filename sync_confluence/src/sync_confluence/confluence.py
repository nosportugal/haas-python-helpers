from __future__ import annotations

import contextlib
import hashlib
import logging
from typing import Optional

from atlassian import Confluence

log = logging.getLogger(__name__)


@contextlib.contextmanager
def _suppress_atlassian_not_found():
    """Silence the atlassian-python-api ERROR logged when a title lookup returns
    no results.  'Not found' is an expected outcome during upsert; real errors
    surface through exceptions, not through that log message."""
    _atlassian_log = logging.getLogger("atlassian.confluence")

    class _Filter(logging.Filter):
        def filter(self, record: logging.LogRecord) -> bool:
            return "Can't find" not in record.getMessage()

    f = _Filter()
    _atlassian_log.addFilter(f)
    try:
        yield
    finally:
        _atlassian_log.removeFilter(f)


def _apply_edit_restriction(
    confluence: Confluence, page_id: str, account_id: str
) -> None:
    """Restrict edit access on the page to the given Atlassian accountId."""
    try:
        response = confluence.request(
            method="PUT",
            path=f"rest/api/content/{page_id}/restriction/byOperation/update/user",
            params={"accountId": account_id},
            advanced_mode=True,
        )
        response.raise_for_status()
        log.debug(
            "Set edit restriction on page id=%s to accountId=%s", page_id, account_id
        )
    except Exception as e:
        log.warning(
            "Could not set edit restriction on page id=%s: %s",
            page_id,
            e,
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
    if not ancestors or str(ancestors[-1]["id"]) != str(parent_id):
        return None

    return {
        "id": str(page["id"]),
        "version": page["version"]["number"],
        "body": page.get("body", {}).get("storage", {}).get("value", ""),
    }


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
    try:
        response = (
            confluence.get(
                path=f"rest/api/content/{parent_id}/child/folder",
                params={"limit": 200, "expand": "version"},
            )
            or {}
        )
        for item in response.get("results", []):
            if item.get("title") == title:
                return {
                    "id": str(item["id"]),
                    "version": item["version"]["number"],
                }
    except Exception as exc:
        log.debug(
            "child/folder endpoint failed for parent %s (%s); trying CQL fallback",
            parent_id,
            exc,
        )

    # Fallback: CQL search scoped to the space and parent
    try:
        cql = (
            f'type=folder AND space.key="{space_key}" '
            f'AND title="{title}" AND parent={parent_id}'
        )
        results = confluence.cql(cql, limit=5) or {}
        for item in results.get("results", []):
            content = item.get("content", item)
            if content.get("title") == title:
                return {"id": str(content["id"]), "version": 1}
    except Exception as exc:
        log.debug("CQL folder search failed for '%s': %s", title, exc)

    return None


def _content_hash(body: str) -> str:
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


# Property key for storing the hash of the generated body
_HASH_PROPERTY_KEY = "sync_confluence_hash"
# Property key for storing the docs-root-relative source file path
_SOURCE_PATH_PROPERTY_KEY = "sync_confluence_source_path"


def _upsert_page_property(
    confluence: Confluence, page_id: str, key: str, value: str
) -> None:
    """Create or update a page property, handling versioning for updates."""
    prop = None
    try:
        prop = confluence.get_page_property(page_id, key)
    except Exception:
        pass  # Property does not exist yet

    if prop and "version" in prop:
        version = prop["version"].get("number", 1)
        response = confluence.request(
            method="PUT",
            path=f"rest/api/content/{page_id}/property/{key}",
            data={"key": key, "value": value, "version": {"number": version + 1}},
            advanced_mode=True,
        )
    else:
        response = confluence.request(
            method="POST",
            path=f"rest/api/content/{page_id}/property",
            data={"key": key, "value": value},
            advanced_mode=True,
        )
    response.raise_for_status()


def _get_child_folders(confluence: Confluence, parent_id: str) -> list[dict]:
    """Return the direct child Confluence Folders under *parent_id*.

    Paginates until all results are fetched.
    """
    results: list[dict] = []
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
        page = response.get("results", [])
        results.extend(page)
        if len(page) < limit:
            break
        start += limit
    return results


def _apply_label(confluence: Confluence, page_id: str, label: str) -> None:
    """Attach *label* to *page_id*; idempotent."""
    confluence.set_page_label(page_id, label)


def _page_has_label(confluence: Confluence, page_id: str, label: str) -> bool:
    """Return ``True`` if *page_id* carries *label*.

    Uses a direct REST call so that both page and folder content types are
    handled correctly.
    """
    try:
        result = confluence.get(path=f"rest/api/content/{page_id}/label") or {}
        return any(entry["name"] == label for entry in result.get("results", []))
    except Exception:
        return False


def _get_source_path_property(confluence: Confluence, page_id: str) -> Optional[str]:
    """Fetch the ``sync_confluence_source_path`` property, or ``None`` if absent."""
    try:
        prop = confluence.get_page_property(page_id, _SOURCE_PATH_PROPERTY_KEY)
        if prop and "value" in prop:
            return prop["value"]
    except Exception:
        pass
    return None


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
    result: dict[str, str] = {}
    limit = 200
    start = 0
    while True:
        try:
            response = (
                confluence.get(
                    path=f"rest/api/content/{parent_id}/child/page",
                    params={"limit": limit, "start": start},
                )
                or {}
            )
        except Exception as exc:
            log.debug(
                "Could not fetch child pages for parent %s to build "
                "source path map: %s",
                parent_id,
                exc,
            )
            break
        pages = response.get("results", [])
        for page in pages:
            page_id = str(page["id"])
            source_path = _get_source_path_property(confluence, page_id)
            if source_path:
                if source_path in result:
                    log.warning(
                        "Duplicate source_path '%s' on pages id=%s and id=%s; "
                        "keeping id=%s for rename detection",
                        source_path,
                        result[source_path],
                        page_id,
                        result[source_path],
                    )
                else:
                    result[source_path] = page_id
        if len(pages) < limit:
            break
        start += limit
    return result


def upsert_page(
    confluence: Confluence,
    space_key: str,
    parent_id: str,
    title: str,
    body: str,
    dry_run: bool = False,
    managed_by_label: Optional[str] = None,
    restrict_edits_to: Optional[str] = None,
    source_path: Optional[str] = None,
    source_path_map: Optional[dict[str, str]] = None,
) -> tuple[Optional[str], str]:
    """Create or update a page.  Returns ``(page_id, action)``.

    *action* is one of ``"created"``, ``"updated"``, ``"unchanged"``, or
    ``"skipped"``.  When *action* is ``"skipped"``, *page_id* is ``None``
    and the page was not touched.  This happens when a page with the same
    title already exists in the space under a **different** parent: hijacking
    and re-parenting that page is forbidden, so the caller is expected to log
    the collision and exclude the file from its results.
    In dry-run mode, *page_id* is ``"DRY-RUN"``.

    When *managed_by_label* is set, the label is applied to every created or
    updated page so that ``delete_orphans`` can safely restrict deletions to
    only pages owned by this automation.

    When *restrict_edits_to* is set (an Atlassian ``accountId``), the page's
    ``update`` restriction is set to allow only that account to edit.  View
    access is left unrestricted.  The restriction is applied on create and
    update; unchanged pages are skipped to avoid unnecessary API calls.
    """
    # DRY-RUN: Simulate lookup and rename logic for accurate reporting
    if dry_run:
        # Simulate title-based lookup
        existing = _find_page_under_parent(confluence, space_key, title, parent_id)
        if not existing and source_path is not None and source_path_map:
            rename_page_id = source_path_map.get(source_path)
            if rename_page_id:
                log.info(
                    "[DRY-RUN] Would rename page id=%s to '%s' and update content",
                    rename_page_id,
                    title,
                )
                if managed_by_label:
                    log.debug(
                        "[DRY-RUN] Would label '%s' with '%s'",
                        title,
                        managed_by_label,
                    )
                if restrict_edits_to:
                    log.debug(
                        "[DRY-RUN] Would restrict edits on '%s' to accountId=%s",
                        title,
                        restrict_edits_to,
                    )
                return ("DRY-RUN", "updated")
        if managed_by_label:
            log.debug("[DRY-RUN] Would label '%s' with '%s'", title, managed_by_label)
        if restrict_edits_to:
            log.debug(
                "[DRY-RUN] Would restrict edits on '%s' to accountId=%s",
                title,
                restrict_edits_to,
            )
        return ("DRY-RUN", "created")

    # Real run: title-based lookup
    existing = _find_page_under_parent(confluence, space_key, title, parent_id)

    # If not found by title, check source_path_map for rename detection.
    # The map is pre-built by the caller (build_source_path_map) from child
    # pages that have the sync_confluence_source_path property set, so this
    # lookup is a single dict.get() with no extra API calls.
    if existing is None and source_path is not None and source_path_map:
        rename_page_id = source_path_map.get(source_path)
        if rename_page_id:
            log.info(
                "Renaming page id=%s to '%s' and updating content",
                rename_page_id,
                title,
            )
            confluence.update_page(
                page_id=rename_page_id,
                title=title,
                body=body,
                parent_id=parent_id,
                representation="storage",
                minor_edit=True,
            )
            try:
                _upsert_page_property(
                    confluence, rename_page_id, _HASH_PROPERTY_KEY, _content_hash(body)
                )
            except Exception as exc:
                log.warning(
                    "Could not set hash property for page id=%s: %s",
                    rename_page_id,
                    exc,
                )
            try:
                _upsert_page_property(
                    confluence, rename_page_id, _SOURCE_PATH_PROPERTY_KEY, source_path
                )
            except Exception as exc:
                log.warning(
                    "Could not set source path property for page id=%s: %s",
                    rename_page_id,
                    exc,
                )
            if managed_by_label:
                _apply_label(confluence, rename_page_id, managed_by_label)
            if restrict_edits_to:
                _apply_edit_restriction(confluence, rename_page_id, restrict_edits_to)
            return (rename_page_id, "updated")

    # Space-wide check: Confluence Cloud enforces space-wide title
    # uniqueness.  If a page with this title exists under a *different*
    # parent we must NOT touch it — re-parenting it would silently move
    # an unrelated page (and all its descendants) into our hierarchy.
    # Treat this as a title collision: warn and skip.
    if existing is None:
        with _suppress_atlassian_not_found():
            _fb = confluence.get_page_by_title(
                space=space_key,
                title=title,
                expand="version",
            )
        if _fb:
            log.warning(
                "Title collision: '%s' already exists in space (id=%s) under a "
                "different parent — skipping this file to avoid hijacking an "
                "unrelated page.",
                title,
                _fb["id"],
            )
            return (None, "skipped")
        log.debug(
            "'%s' not found in space, will create under parent %s", title, parent_id
        )

    if existing:
        # Compare against the stored hash to skip no-op updates.
        # We store the hash of the generated body in a page property rather
        # than comparing against the body fetched from Confluence, because
        # Confluence normalises the storage format on save — making a direct
        # round-trip comparison permanently unstable.
        prop_val = None
        try:
            prop = confluence.get_page_property(existing["id"], _HASH_PROPERTY_KEY)
            if prop and "value" in prop:
                prop_val = prop["value"]
        except Exception as exc:
            log.warning(
                "Could not fetch hash property for page id=%s (%s); will update",
                existing["id"],
                exc,
            )

        if prop_val == _content_hash(body):
            log.debug("Unchanged: '%s' (id=%s)", title, existing["id"])
            return (existing["id"], "unchanged")

        confluence.update_page(
            page_id=existing["id"],
            title=title,
            body=body,
            parent_id=parent_id,
            representation="storage",
            minor_edit=True,
        )
        log.info("Updated: '%s' (id=%s)", title, existing["id"])
        try:
            _upsert_page_property(
                confluence,
                existing["id"],
                _HASH_PROPERTY_KEY,
                _content_hash(body),
            )
        except Exception as exc:
            log.warning(
                "Could not set hash property for page id=%s: %s", existing["id"], exc
            )
        if source_path is not None:
            try:
                _upsert_page_property(
                    confluence,
                    existing["id"],
                    _SOURCE_PATH_PROPERTY_KEY,
                    source_path,
                )
            except Exception as exc:
                log.warning(
                    "Could not set source path property for page id=%s: %s",
                    existing["id"],
                    exc,
                )
        if managed_by_label:
            _apply_label(confluence, existing["id"], managed_by_label)
        if restrict_edits_to:
            _apply_edit_restriction(confluence, existing["id"], restrict_edits_to)
        return (existing["id"], "updated")

    page = confluence.create_page(
        space=space_key,
        title=title,
        body=body,
        parent_id=parent_id,
        representation="storage",
    )
    page_id = str(page["id"])
    log.info("Created: '%s' (id=%s)", title, page_id)
    try:
        _upsert_page_property(
            confluence, page_id, _HASH_PROPERTY_KEY, _content_hash(body)
        )
    except Exception as exc:
        log.warning("Could not set hash property for page id=%s: %s", page_id, exc)
    if source_path is not None:
        try:
            _upsert_page_property(
                confluence, page_id, _SOURCE_PATH_PROPERTY_KEY, source_path
            )
        except Exception as exc:
            log.warning(
                "Could not set source path property for page id=%s: %s", page_id, exc
            )
    if managed_by_label:
        _apply_label(confluence, page_id, managed_by_label)
    if restrict_edits_to:
        _apply_edit_restriction(confluence, page_id, restrict_edits_to)
    return (page_id, "created")


def upsert_folder(
    confluence: Confluence,
    space_key: str,
    parent_id: str,
    title: str,
    dry_run: bool = False,
    managed_by_label: Optional[str] = None,
    source_path: Optional[str] = None,
) -> tuple[str, str]:
    """Create or find a Confluence Folder.  Returns ``(folder_id, action)``.

    *action* is one of ``"created"`` or ``"unchanged"``.
    In dry-run mode, *folder_id* is ``"DRY-RUN"``.

    Folders have no editable body content, so no edit restriction is applied.
    The *managed_by_label* is attached on creation so that ``delete_orphans``
    can identify and clean up stale folders.
    """
    if dry_run:
        if managed_by_label:
            log.debug(
                "[DRY-RUN] Would label folder '%s' with '%s'",
                title,
                managed_by_label,
            )
        return ("DRY-RUN", "created")

    existing = _find_folder_under_parent(confluence, space_key, title, parent_id)
    if existing:
        log.debug("Unchanged folder: '%s' (id=%s)", title, existing["id"])
        # Re-apply label so it is self-healing if it was ever missing.
        if managed_by_label:
            _apply_label(confluence, existing["id"], managed_by_label)
        if source_path is not None:
            try:
                _upsert_page_property(
                    confluence,
                    existing["id"],
                    _SOURCE_PATH_PROPERTY_KEY,
                    source_path,
                )
            except Exception as exc:
                log.warning(
                    "Could not set source path property for folder id=%s: %s",
                    existing["id"],
                    exc,
                )
        return (existing["id"], "unchanged")

    from requests.exceptions import HTTPError

    try:
        item = confluence.post(
            path="rest/api/content",
            data={
                "type": "folder",
                "title": title,
                "space": {"key": space_key},
                "ancestors": [{"id": parent_id}],
            },
        )
        folder_id = str(item["id"])
        log.info("Created folder: '%s' (id=%s)", title, folder_id)
        if managed_by_label:
            _apply_label(confluence, folder_id, managed_by_label)
        if source_path is not None:
            try:
                _upsert_page_property(
                    confluence, folder_id, _SOURCE_PATH_PROPERTY_KEY, source_path
                )
            except Exception as exc:
                log.warning(
                    "Could not set source path property for folder id=%s: %s",
                    folder_id,
                    exc,
                )
        return (folder_id, "created")
    except HTTPError as exc:
        # Confluence Cloud rejects the create if a folder with this title
        # already exists anywhere in the space, even when our child-folder
        # lookup didn't find it (endpoint unreliable for some tenants).
        # Attempt a second, broader lookup before giving up.
        has_response = exc.response is not None
        if "folder exists" in str(exc).lower() or (
            has_response and exc.response.status_code in (400, 409)
        ):
            log.debug(
                "Folder '%s' creation rejected (%s); attempting broader lookup",
                title,
                exc,
            )
            # Try CQL space-wide (ignoring parent constraint)
            try:
                cql = f'type=folder AND space.key="{space_key}" AND title="{title}"'
                results = confluence.cql(cql, limit=5) or {}
                for item in results.get("results", []):
                    content = item.get("content", item)
                    if content.get("title") == title:
                        folder_id = str(content["id"])
                        log.info(
                            "Found existing folder '%s' via CQL (id=%s)",
                            title,
                            folder_id,
                        )
                        return (folder_id, "unchanged")
            except Exception as cql_exc:
                log.debug("CQL fallback also failed: %s", cql_exc)
        raise


def _collect_children(confluence: Confluence, page_id: str) -> list[dict]:
    """Recursively collect all descendant pages and folders under *page_id*.

    Returns a flat list of ``{"id", "title"}`` dicts ordered leaves-first
    (safe for bottom-up deletion).  Both pages and Confluence Folder objects
    are included so that orphan cleanup can remove stale folders.
    """
    result: list[dict] = []
    try:
        pages = confluence.get_child_pages(page_id) or []
    except Exception:
        pages = []
    folders = _get_child_folders(confluence, page_id)

    for child in list(pages) + list(folders):
        child_id = str(child["id"])
        grandchildren = _collect_children(confluence, child_id)
        # Append grandchildren first (depth-first / leaves-first)
        result.extend(grandchildren)
        result.append({"id": child_id, "title": child["title"]})

    return result


def delete_orphans(
    confluence: Confluence,
    root_page_id: str,
    expected_titles: set[str],
    dry_run: bool = False,
    managed_by_label: Optional[str] = None,
    expected_paths: Optional[set[str]] = None,
) -> int:
    """Delete pages under *root_page_id* whose titles are not in
    *expected_titles* and whose source paths are not in *expected_paths*.

    Deletes bottom-up to avoid cascade issues.  Returns the count of deleted
    pages.

    When *managed_by_label* is set, only pages that carry that label are
    eligible for deletion.  Pages created outside this automation are left
    untouched even if their title is not in *expected_titles*.

    When *expected_paths* is set, each candidate's
    ``sync_confluence_source_path`` page property is checked before deletion.
    A page whose stored source path is still in *expected_paths* is kept even
    if its title changed (rename detection).  Pages that pre-date this feature
    and carry no source path property fall back to title-matching only.
    """
    all_pages = _collect_children(confluence, root_page_id)
    deleted = 0

    for page in all_pages:
        if page["title"] in expected_titles:
            continue

        if expected_paths is not None:
            source_path = _get_source_path_property(confluence, page["id"])
            if source_path is not None and source_path in expected_paths:
                log.debug(
                    "Keeping '%s' (id=%s) — source path '%s' still exists",
                    page["title"],
                    page["id"],
                    source_path,
                )
                continue

        if managed_by_label and not _page_has_label(
            confluence, page["id"], managed_by_label
        ):
            log.debug(
                "Skipping non-managed page: '%s' (id=%s)",
                page["title"],
                page["id"],
            )
            continue

        if dry_run:
            log.info(
                "[DRY-RUN] Would delete orphan: '%s' (id=%s)",
                page["title"],
                page["id"],
            )
        else:
            confluence.remove_page(page["id"])
            log.info("Deleted orphan: '%s' (id=%s)", page["title"], page["id"])
        deleted += 1

    return deleted
