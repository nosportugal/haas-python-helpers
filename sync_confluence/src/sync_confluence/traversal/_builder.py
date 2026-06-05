"""Builders for page/folder upsert requests and source-path maps."""

from __future__ import annotations

from pathlib import Path

from sync_confluence.confluence import (
    FolderUpsertRequest,
    PageUpsertRequest,
    build_source_path_map,
)
from sync_confluence.converter import (
    ConversionResult,
    ConverterOptions,
    RepoContext,
    SourcePaths,
    convert_markdown,
    derive_title,
)
from sync_confluence.traversal._state import SyncContext

_DRY_RUN_ID = "DRY-RUN"


def _collect_md_files(directory: Path, readme_as_parent: bool) -> list[Path]:
    """Sorted ``.md`` files under *directory*; skip README when it's the parent."""
    if readme_as_parent:
        return sorted(
            md_path for md_path in directory.glob("*.md") if md_path.name != "README.md"
        )
    return sorted(directory.glob("*.md"))


class _RequestBuilder:
    """Builds page/folder requests from a :class:`SyncContext`.

    *allow_root_title* controls whether a ``README.md`` encountered in the
    md-files loop should inherit ``ctx.root_title``.  The top-level walk sets
    it to ``True``; sub-walks and :func:`sync_files` set it to ``False`` so
    nested READMEs are treated as regular leaves.
    """

    def __init__(self, ctx: SyncContext, *, allow_root_title: bool) -> None:
        self._ctx = ctx
        self._allow_root_title = allow_root_title

    def render(self, md_file: Path) -> ConversionResult:
        options = ConverterOptions(
            paths=SourcePaths(current_file=md_file, docs_root=self._ctx.docs_root),
            repo=RepoContext(repo_url=self._ctx.repo_url, git_ref=self._ctx.git_ref),
            doc_index=self._ctx.doc_index,
            mermaid_macro=self._ctx.mermaid_macro,
            generated_by=self._ctx.generated_by,
        )
        return convert_markdown(md_file.read_text(encoding="utf-8"), options)

    def resolve_md_title(self, md_file: Path) -> str:
        if self._allow_root_title and md_file.name == "README.md":
            return derive_title(md_file, self._ctx.docs_root, self._ctx.root_title)
        return derive_title(md_file, self._ctx.docs_root, None)

    def build_readme_request(
        self, parent_id: str, readme: Path, title: str
    ) -> PageUpsertRequest:
        rendered = self.render(readme)
        return PageUpsertRequest(
            space_key=self._ctx.space_key,
            parent_id=parent_id,
            title=title,
            body=rendered.body,
            dry_run=self._ctx.dry_run,
            managed_by_label=self._ctx.managed_by_label,
            restrict_edits_to=self._ctx.restrict_edits_to,
            source_path=str(readme.relative_to(self._ctx.docs_root)),
            page_width=self._ctx.page_width,
            attachments=rendered.attachments,
        )

    def build_page_request(
        self,
        parent_id: str,
        md_file: Path,
        title: str,
        source_path_map: dict[str, str],
    ) -> PageUpsertRequest:
        rendered = self.render(md_file)
        return PageUpsertRequest(
            space_key=self._ctx.space_key,
            parent_id=parent_id,
            title=title,
            body=rendered.body,
            dry_run=self._ctx.dry_run,
            managed_by_label=self._ctx.managed_by_label,
            restrict_edits_to=self._ctx.restrict_edits_to,
            source_path=str(md_file.relative_to(self._ctx.docs_root)),
            source_path_map=source_path_map,
            page_width=self._ctx.page_width,
            attachments=rendered.attachments,
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
