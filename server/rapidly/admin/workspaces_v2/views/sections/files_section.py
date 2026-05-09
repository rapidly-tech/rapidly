"""Files section with file listing, download links, and storage stats."""

import contextlib
from collections.abc import Generator

from fastapi import Request
from starlette.datastructures import URL
from tagflow import attr, tag, text

from rapidly.catalog.file import actions as file_service
from rapidly.models import File, Workspace

from ....components import card, empty_state
from ....formatters import file_size as _human_size

# Table column headers shown in the files listing.
_FILE_TABLE_HEADERS: list[str] = ["Name", "Type", "Size", "Created", "Actions"]


class FilesSection:
    """Render the files section with file listing and storage summary."""

    def __init__(
        self,
        workspace: Workspace,
        files: list[File] | None = None,
        page: int = 1,
        limit: int = 10,
        total_count: int = 0,
    ):
        self._workspace = workspace
        self._files = files or []
        self._page = page
        self._limit = limit
        self._total_count = total_count

    # -- keep public API for callers that used .format_file_size --
    @staticmethod
    def format_file_size(size_bytes: int) -> str:
        return _human_size(size_bytes)

    # -- pagination --

    def _page_nav_urls(self, request: Request) -> tuple[URL | None, URL | None]:
        """Return (previous_url, next_url) for pagination buttons."""
        start = (self._page - 1) * self._limit + 1
        end = min(self._page * self._limit, self._total_count)
        prev_url: URL | None = None
        next_url: URL | None = None
        if start > 1:
            prev_url = request.url.replace_query_params(
                **{**request.query_params, "files_page": self._page - 1}
            ).replace(fragment="files")
        if end < self._total_count:
            next_url = request.url.replace_query_params(
                **{**request.query_params, "files_page": self._page + 1}
            ).replace(fragment="files")
        return prev_url, next_url

    def _render_pagination(self, request: Request) -> None:
        start = (self._page - 1) * self._limit + 1
        end = min(self._page * self._limit, self._total_count)
        prev_url, next_url = self._page_nav_urls(request)

        with tag.div(classes="flex justify-between"):
            with tag.div(classes="text-sm"):
                text("Showing ")
                with tag.span(classes="font-bold"):
                    text(str(start))
                text(" to ")
                with tag.span(classes="font-bold"):
                    text(str(end))
                text(" of ")
                with tag.span(classes="font-bold"):
                    text(str(self._total_count))
                text(" entries")
            with tag.div(classes="join grid grid-cols-2"):
                with tag.a(
                    classes="join-item btn",
                    href=str(prev_url) if prev_url else "",
                ):
                    if prev_url is None:
                        attr("disabled", True)
                    text("Previous")
                with tag.a(
                    classes="join-item btn",
                    href=str(next_url) if next_url else "",
                ):
                    if next_url is None:
                        attr("disabled", True)
                    text("Next")

    # -- file rows --

    def _render_file_row(self, f: File) -> None:
        download_url, _ = file_service.generate_download_url(f)
        with tag.tr():
            with tag.td():
                with tag.div(classes="font-medium"):
                    text(f.name)
            with tag.td():
                with tag.span(classes="badge badge-sm badge-ghost"):
                    text(f.mime_type or "unknown")
            with tag.td():
                text(_human_size(f.size) if f.size else "N/A")
            with tag.td():
                text(f.created_at.strftime("%Y-%m-%d") if f.created_at else "N/A")
            with tag.td():
                with tag.a(
                    href=download_url,
                    target="_blank",
                    rel="noopener noreferrer",
                    classes="btn btn-sm btn-ghost",
                ):
                    text("Download")

    # -- main render --

    @contextlib.contextmanager
    def render(self, request: Request) -> Generator[None]:
        with tag.div(classes="space-y-6", id="files"):
            # Files list card
            with card(bordered=True):
                with tag.div(classes="flex items-center justify-between mb-4"):
                    with tag.h2(classes="text-lg font-bold"):
                        text("Downloadable Files")
                    with tag.div(classes="text-sm text-base-content/60"):
                        text(f"{self._total_count} file(s)")

                if self._files:
                    with tag.div(classes="overflow-x-auto"):
                        with tag.table(classes="table table-zebra w-full"):
                            with tag.thead():
                                with tag.tr():
                                    for hdr in _FILE_TABLE_HEADERS:
                                        with tag.th():
                                            text(hdr)
                            with tag.tbody():
                                for f in self._files:
                                    self._render_file_row(f)

                    if self._total_count > self._limit:
                        self._render_pagination(request)
                else:
                    with empty_state(
                        "No Files",
                        "This workspace hasn't uploaded any downloadable files yet.",
                    ):
                        pass

            # Storage summary
            with card(bordered=True):
                with tag.h3(classes="text-md font-bold mb-3"):
                    text("Storage Information")
                page_bytes = sum(f.size for f in self._files if f.size)
                with tag.div(classes="space-y-2 text-sm"):
                    with tag.div(classes="flex justify-between"):
                        with tag.span(classes="text-base-content/60"):
                            text("Total Files:")
                        with tag.span(classes="font-semibold"):
                            text(str(self._total_count))
                    with tag.div(classes="flex justify-between"):
                        with tag.span(classes="text-base-content/60"):
                            text("Page Size:")
                        with tag.span(classes="font-semibold"):
                            text(_human_size(page_bytes))

            yield


__all__ = ["FilesSection"]
