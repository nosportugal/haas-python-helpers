"""Builders for page/folder upsert requests and source-path maps."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from sync_confluence.confluence import (
    FolderUpsertRequest,
    PageUpsertRequest,
    build_source_path_map,
)
from sync_confluence.converter import convert_markdown, derive_title
from sync_confluence.traversal._diagrams import (
    extract_mermaid_blocks,
    mermaid_attachment_filename,
    render_mermaid_svg,
)
from sync_confluence.traversal._images import (
    SUPPORTED_LOCAL_IMAGE_EXTENSIONS,
    extract_local_image_paths,
    local_image_attachment_filename,
)
from sync_confluence.traversal._state import SyncContext

log = logging.getLogger(__name__)

_DRY_RUN_ID = "DRY-RUN"


@dataclass
class _AttachedPageRequest:
    """A page upsert request paired with its attachment payload."""

    request: PageUpsertRequest
    attachments: dict[str, bytes] = field(default_factory=dict)  # filename → raw bytes


def _collect_md_files(directory: Path, readme_as_parent: bool) -> list[Path]:
    """Sorted ``.md`` files under *directory*; skip README when it's the parent."""
    if readme_as_parent:
        return sorted(
            md_path for md_path in directory.glob("*.md") if md_path.name != "README.md"
        )
    return sorted(directory.glob("*.md"))


class _RequestBuilder:  # noqa: WPS214 — builder needs init + render + resolve + 4 build methods + private helper
    """Builds page/folder requests from a :class:`SyncContext`.

    *allow_root_title* controls whether a ``README.md`` encountered in the
    md-files loop should inherit ``ctx.root_title``.  The top-level walk sets
    it to ``True``; sub-walks and :func:`sync_files` set it to ``False`` so
    nested READMEs are treated as regular leaves.
    """

    def __init__(self, ctx: SyncContext, *, allow_root_title: bool) -> None:
        self._ctx = ctx
        self._allow_root_title = allow_root_title

    def render(self, md_file: Path) -> str:
        return convert_markdown(
            md_file.read_text(encoding="utf-8"),
            mermaid_macro=self._ctx.mermaid_macro,
            repo_url=self._ctx.repo_url,
            git_ref=self._ctx.git_ref,
            current_file=md_file,
        )

    def resolve_md_title(self, md_file: Path) -> str:
        if self._allow_root_title and md_file.name == "README.md":
            return derive_title(md_file, self._ctx.docs_root, self._ctx.root_title)
        return derive_title(md_file, self._ctx.docs_root, None)

    def build_readme_request(
        self, parent_id: str, readme: Path, title: str
    ) -> _AttachedPageRequest:
        text = readme.read_text(encoding="utf-8")
        mermaid_attachments, image_attachments, upload_data = (
            self._collect_attachments(readme, text)
            if self._ctx.upload_attachments
            else ({}, {}, {})
        )
        body = convert_markdown(
            text,
            mermaid_macro=self._ctx.mermaid_macro,
            mermaid_attachments=mermaid_attachments or None,
            image_attachments=image_attachments or None,
            repo_url=self._ctx.repo_url,
            git_ref=self._ctx.git_ref,
            current_file=readme,
        )
        return _AttachedPageRequest(
            request=PageUpsertRequest(
                space_key=self._ctx.space_key,
                parent_id=parent_id,
                title=title,
                body=body,
                dry_run=self._ctx.dry_run,
                managed_by_label=self._ctx.managed_by_label,
                restrict_edits_to=self._ctx.restrict_edits_to,
                source_path=str(readme.relative_to(self._ctx.docs_root)),
                page_width=self._ctx.page_width,
            ),
            attachments=upload_data,
        )

    def build_page_request(
        self,
        parent_id: str,
        md_file: Path,
        title: str,
        source_path_map: dict[str, str],
    ) -> _AttachedPageRequest:
        text = md_file.read_text(encoding="utf-8")
        mermaid_attachments, image_attachments, upload_data = (
            self._collect_attachments(md_file, text)
            if self._ctx.upload_attachments
            else ({}, {}, {})
        )
        body = convert_markdown(
            text,
            mermaid_macro=self._ctx.mermaid_macro,
            mermaid_attachments=mermaid_attachments or None,
            image_attachments=image_attachments or None,
            repo_url=self._ctx.repo_url,
            git_ref=self._ctx.git_ref,
            current_file=md_file,
        )
        return _AttachedPageRequest(
            request=PageUpsertRequest(
                space_key=self._ctx.space_key,
                parent_id=parent_id,
                title=title,
                body=body,
                dry_run=self._ctx.dry_run,
                managed_by_label=self._ctx.managed_by_label,
                restrict_edits_to=self._ctx.restrict_edits_to,
                source_path=str(md_file.relative_to(self._ctx.docs_root)),
                source_path_map=source_path_map,
                page_width=self._ctx.page_width,
            ),
            attachments=upload_data,
        )

    def build_folder_request(
        self, parent_id: str, subdir: Path, folder_title: str
    ) -> FolderUpsertRequest:
        return FolderUpsertRequest(
            space_key=self._ctx.space_key,
            parent_id=parent_id,
            title=folder_title,
            dry_run=self._ctx.dry_run,
            managed_by_label=self._ctx.managed_by_label,
            source_path=str(subdir.relative_to(self._ctx.docs_root)),
        )

    def build_path_map(self, page_id: str) -> dict[str, str]:
        if self._ctx.dry_run or page_id == _DRY_RUN_ID:
            return {}
        return build_source_path_map(self._ctx.confluence, page_id)

    def _collect_attachments(  # noqa: WPS210, WPS231 — two parallel loops; complexity is inherent
        self, md_file: Path, text: str
    ) -> tuple[dict[str, str], dict[str, str], dict[str, bytes]]:  # noqa: WPS221
        """Scan *text* for mermaid blocks and local images; render / read them.

        Returns a 3-tuple:
        - *mermaid_attachments*: ``{unescaped_source: filename}``
        - *image_attachments*: ``{rel_path: filename}``
        - *upload_data*: ``{filename: bytes}`` — the payload to upload
        """
        mermaid_att: dict[str, str] = {}  # noqa: WPS221
        image_att: dict[str, str] = {}  # noqa: WPS221
        upload_data: dict[str, bytes] = {}  # noqa: WPS221

        # --- Mermaid blocks ---
        if self._ctx.mmdc_path:
            for source in extract_mermaid_blocks(text):
                filename = mermaid_attachment_filename(source)
                svg_bytes = render_mermaid_svg(source, self._ctx.mmdc_path)
                if svg_bytes is not None:
                    mermaid_att[source] = filename
                    upload_data[filename] = svg_bytes

        # --- Local images ---
        for rel_path in extract_local_image_paths(text):
            suffix = Path(rel_path).suffix.lower()
            if suffix not in SUPPORTED_LOCAL_IMAGE_EXTENSIONS:
                log.debug(
                    "Skipping unsupported image extension %s: %s", suffix, rel_path
                )
                continue
            abs_path = md_file.parent / rel_path
            if not abs_path.is_file():
                log.warning("Local image not found, skipping: %s", abs_path)
                continue
            filename = local_image_attachment_filename(rel_path)
            image_att[rel_path] = filename
            upload_data[filename] = abs_path.read_bytes()

        return mermaid_att, image_att, upload_data
