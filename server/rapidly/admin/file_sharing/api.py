"""Admin panel admin endpoints for file sharing sessions."""

from collections.abc import Generator
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import UUID4
from tagflow import classes, tag, text

from rapidly.core.pagination import PaginationParamsQuery
from rapidly.core.utils import now_utc
from rapidly.models.file_share_report import FileShareReportStatus
from rapidly.models.file_share_session import FileShareSession, FileShareSessionStatus
from rapidly.postgres import (
    AsyncReadSession,
    AsyncSession,
    get_db_read_session,
    get_db_session,
)
from rapidly.sharing.file_sharing.ordering import ListSorting
from rapidly.sharing.file_sharing.pg_repository import (
    FileShareDownloadRepository,
    FileSharePaymentRepository,
    FileShareReportRepository,
    FileShareSessionRepository,
    FileShareSessionSortProperty,
)

from ..components import button, datatable, input
from ..layout import layout
from ..responses import HXRedirectResponse
from ..toast import add_toast
from .queries import AdminFileShareSessionRepository

router = APIRouter()


# ── List ──


class SessionStatusColumn(
    datatable.DatatableSortingColumn[FileShareSession, FileShareSessionSortProperty]
):
    def render(
        self, request: Request, item: FileShareSession
    ) -> Generator[None] | None:
        status = (
            item.status.value if hasattr(item.status, "value") else str(item.status)
        )
        with tag.div(classes="badge"):
            if item.status == FileShareSessionStatus.active:
                classes("badge-success")
            elif item.status == FileShareSessionStatus.created:
                classes("badge-info")
            elif item.status == FileShareSessionStatus.expired:
                classes("badge-warning")
            elif item.status == FileShareSessionStatus.destroyed:
                classes("badge-neutral")
            elif item.status == FileShareSessionStatus.reported:
                classes("badge-error")
            elif item.status == FileShareSessionStatus.completed:
                classes("badge-success")
            text(status)
        return None


class PriceColumn(datatable.DatatableColumn[FileShareSession]):
    def render(
        self, request: Request, item: FileShareSession
    ) -> Generator[None] | None:
        if item.price_cents is not None and item.price_cents > 0:
            text(f"${item.price_cents / 100:.2f} {item.currency.upper()}")
        else:
            with tag.span(classes="text-gray-400"):
                text("Free")
        return None


@router.get("/", name="file_sharing:list")
async def list_sessions(
    request: Request,
    pagination: PaginationParamsQuery,
    sorting: ListSorting,
    query: str | None = Query(None),
    status: str | None = Query(None),
    session: AsyncReadSession = Depends(get_db_read_session),
) -> None:
    admin_repo = AdminFileShareSessionRepository.from_session(session)
    stmt = admin_repo.get_list_statement(query=query, status=status)

    domain_repo = FileShareSessionRepository.from_session(session)
    stmt = domain_repo.apply_sorting(stmt, sorting)

    items, count = await admin_repo.paginate(
        stmt, limit=pagination.limit, page=pagination.page
    )

    with layout(
        request,
        [("File Sharing", str(request.url_for("file_sharing:list")))],
        "file_sharing:list",
    ):
        with tag.div(classes="flex flex-col gap-4"):
            with tag.h1(classes="text-4xl"):
                text("File Sharing Sessions")

            with tag.form(method="GET", classes="w-full flex flex-row gap-2"):
                with input.search("query", query):
                    pass
                status_options = [("All Statuses", "")] + [
                    (s.value.title(), s.value) for s in FileShareSessionStatus
                ]
                with input.select(
                    status_options,
                    status or "",
                    name="status",
                ):
                    pass
                with button(type="submit"):
                    text("Filter")

            with datatable.Datatable[FileShareSession, FileShareSessionSortProperty](
                datatable.DatatableAttrColumn(
                    "short_slug",
                    "Short Slug",
                    href_route_name="file_sharing:detail",
                ),
                datatable.DatatableAttrColumn("long_slug", "Long Slug"),
                SessionStatusColumn(
                    "Status", sorting=FileShareSessionSortProperty.status
                ),
                datatable.DatatableAttrColumn(
                    "download_count",
                    "Downloads",
                    sorting=FileShareSessionSortProperty.download_count,
                ),
                PriceColumn("Price"),
                datatable.DatatableAttrColumn("file_name", "File Name"),
                datatable.DatatableDateTimeColumn(
                    "created_at",
                    "Created",
                    sorting=FileShareSessionSortProperty.created_at,
                ),
            ).render(request, items, sorting=sorting):
                pass
            with datatable.pagination(request, pagination, count):
                pass


# ── Detail ──


@router.get("/{id}", name="file_sharing:detail")
async def detail(
    request: Request,
    id: UUID4,
    session: AsyncReadSession = Depends(get_db_read_session),
) -> None:
    repo = FileShareSessionRepository.from_session(session)
    fs_session = await repo.get_by_id(id)
    if fs_session is None:
        raise HTTPException(status_code=404)

    # Load related data
    download_repo = FileShareDownloadRepository.from_session(session)
    downloads = await download_repo.get_by_session_id(id)

    payment_repo = FileSharePaymentRepository.from_session(session)
    payments = await payment_repo.get_by_session_id(id)

    report_repo = FileShareReportRepository.from_session(session)
    reports = await report_repo.get_by_session_id(id)

    with layout(
        request,
        [
            ("File Sharing", str(request.url_for("file_sharing:list"))),
            (fs_session.short_slug, str(request.url)),
        ],
        "file_sharing:detail",
    ):
        with tag.div(classes="flex flex-col gap-6"):
            # Header
            with tag.div(classes="flex justify-between items-center"):
                with tag.h1(classes="text-4xl"):
                    text(f"Session: {fs_session.short_slug}")

                with tag.div(classes="flex items-center gap-3"):
                    # Status badge
                    status_val = (
                        fs_session.status.value
                        if hasattr(fs_session.status, "value")
                        else str(fs_session.status)
                    )
                    with tag.div(classes="badge badge-lg"):
                        if fs_session.status == FileShareSessionStatus.active:
                            classes("badge-success")
                        elif fs_session.status == FileShareSessionStatus.reported:
                            classes("badge-error")
                        elif fs_session.status == FileShareSessionStatus.expired:
                            classes("badge-warning")
                        text(status_val)

                    # Admin actions
                    if fs_session.status in (
                        FileShareSessionStatus.created,
                        FileShareSessionStatus.active,
                    ):
                        with button(
                            variant="warning",
                            size="sm",
                            hx_post=str(
                                request.url_for(
                                    "file_sharing:force_expire", id=fs_session.id
                                )
                            ),
                            hx_confirm="Force-expire this session? It will no longer accept downloads.",
                        ):
                            text("Force Expire")
                    if fs_session.status not in (FileShareSessionStatus.destroyed,):
                        with button(
                            variant="error",
                            size="sm",
                            hx_post=str(
                                request.url_for(
                                    "file_sharing:force_destroy", id=fs_session.id
                                )
                            ),
                            hx_confirm="Destroy this session? This cannot be undone.",
                        ):
                            text("Destroy")

            # Session details
            with tag.div(classes="card bg-base-100 shadow-xl"):
                with tag.div(classes="card-body"):
                    with tag.h2(classes="card-title"):
                        text("Session Details")

                    with tag.div(classes="grid grid-cols-2 gap-4"):
                        _detail_field("ID", str(fs_session.id))
                        _detail_field("Short Slug", fs_session.short_slug)
                        _detail_field("Long Slug", fs_session.long_slug)
                        _detail_field("Status", status_val)
                        _detail_field("Max Downloads", str(fs_session.max_downloads))
                        _detail_field("Download Count", str(fs_session.download_count))
                        _detail_field(
                            "Price",
                            f"${fs_session.price_cents / 100:.2f} {fs_session.currency.upper()}"
                            if fs_session.price_cents
                            else "Free",
                        )
                        _detail_field("File Name", fs_session.file_name or "N/A")
                        _detail_field(
                            "File Size",
                            f"{fs_session.file_size_bytes:,} bytes"
                            if fs_session.file_size_bytes
                            else "N/A",
                        )
                        _detail_field(
                            "TTL",
                            f"{fs_session.ttl_seconds}s"
                            if fs_session.ttl_seconds
                            else "N/A",
                        )
                        _detail_field(
                            "Expires At",
                            fs_session.expires_at.strftime("%Y-%m-%d %H:%M:%S")
                            if fs_session.expires_at
                            else "N/A",
                        )
                        _detail_field(
                            "Created At",
                            fs_session.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                        )
                        _detail_field(
                            "User ID",
                            str(fs_session.user_id) if fs_session.user_id else "N/A",
                        )
                        _detail_field(
                            "Workspace ID",
                            str(fs_session.workspace_id)
                            if fs_session.workspace_id
                            else "N/A",
                        )

            # Downloads
            if downloads:
                with tag.div(classes="card bg-base-100 shadow-xl"):
                    with tag.div(classes="card-body"):
                        with tag.h2(classes="card-title"):
                            text(f"Downloads ({len(downloads)})")
                        with tag.div(classes="overflow-x-auto"):
                            with tag.table(classes="table table-zebra"):
                                with tag.thead():
                                    with tag.tr():
                                        with tag.th():
                                            text("Slot")
                                        with tag.th():
                                            text("Created")
                                with tag.tbody():
                                    for dl in downloads:
                                        with tag.tr():
                                            with tag.td():
                                                text(str(dl.slot_number))
                                            with tag.td():
                                                text(
                                                    dl.created_at.strftime(
                                                        "%Y-%m-%d %H:%M:%S"
                                                    )
                                                )

            # Payments
            if payments:
                with tag.div(classes="card bg-base-100 shadow-xl"):
                    with tag.div(classes="card-body"):
                        with tag.h2(classes="card-title"):
                            text(f"Payments ({len(payments)})")
                        with tag.div(classes="overflow-x-auto"):
                            with tag.table(classes="table table-zebra"):
                                with tag.thead():
                                    with tag.tr():
                                        with tag.th():
                                            text("Amount")
                                        with tag.th():
                                            text("Status")
                                        with tag.th():
                                            text("Stripe Session")
                                        with tag.th():
                                            text("Created")
                                with tag.tbody():
                                    for payment in payments:
                                        with tag.tr():
                                            with tag.td():
                                                text(
                                                    f"${payment.amount_cents / 100:.2f} {payment.currency.upper()}"
                                                )
                                            with tag.td():
                                                status_text = (
                                                    payment.status.value
                                                    if hasattr(payment.status, "value")
                                                    else str(payment.status)
                                                )
                                                with tag.div(classes="badge"):
                                                    text(status_text)
                                            with tag.td():
                                                text(
                                                    payment.stripe_checkout_session_id
                                                    or "N/A"
                                                )
                                            with tag.td():
                                                text(
                                                    payment.created_at.strftime(
                                                        "%Y-%m-%d %H:%M:%S"
                                                    )
                                                )

            # Reports
            if reports:
                with tag.div(classes="card bg-base-100 shadow-xl"):
                    with tag.div(classes="card-body"):
                        with tag.h2(classes="card-title"):
                            text(f"Reports ({len(reports)})")
                        with tag.div(classes="overflow-x-auto"):
                            with tag.table(classes="table table-zebra"):
                                with tag.thead():
                                    with tag.tr():
                                        with tag.th():
                                            text("Status")
                                        with tag.th():
                                            text("Reason")
                                        with tag.th():
                                            text("Created")
                                        with tag.th():
                                            text("Reviewed")
                                        with tag.th():
                                            text("Actions")
                                with tag.tbody():
                                    for report in reports:
                                        with tag.tr():
                                            with tag.td():
                                                report_status = (
                                                    report.status.value
                                                    if hasattr(report.status, "value")
                                                    else str(report.status)
                                                )
                                                with tag.div(classes="badge"):
                                                    if (
                                                        report.status
                                                        == FileShareReportStatus.pending
                                                    ):
                                                        classes("badge-warning")
                                                    elif (
                                                        report.status
                                                        == FileShareReportStatus.actioned
                                                    ):
                                                        classes("badge-error")
                                                    elif (
                                                        report.status
                                                        == FileShareReportStatus.reviewed
                                                    ):
                                                        classes("badge-success")
                                                    elif (
                                                        report.status
                                                        == FileShareReportStatus.dismissed
                                                    ):
                                                        classes("badge-neutral")
                                                    text(report_status)
                                            with tag.td():
                                                text(report.reason or "N/A")
                                            with tag.td():
                                                text(
                                                    report.created_at.strftime(
                                                        "%Y-%m-%d %H:%M:%S"
                                                    )
                                                )
                                            with tag.td():
                                                text(
                                                    report.reviewed_at.strftime(
                                                        "%Y-%m-%d %H:%M:%S"
                                                    )
                                                    if report.reviewed_at
                                                    else "Pending"
                                                )
                                            with tag.td():
                                                if (
                                                    report.status
                                                    == FileShareReportStatus.pending
                                                ):
                                                    with tag.div(classes="flex gap-1"):
                                                        with button(
                                                            variant="success",
                                                            size="xs",
                                                            hx_post=str(
                                                                request.url_for(
                                                                    "file_sharing:review_report",
                                                                    id=fs_session.id,
                                                                    report_id=report.id,
                                                                )
                                                            ),
                                                            hx_confirm="Mark this report as reviewed?",
                                                        ):
                                                            text("Review")
                                                        with button(
                                                            variant="secondary",
                                                            size="xs",
                                                            hx_post=str(
                                                                request.url_for(
                                                                    "file_sharing:dismiss_report",
                                                                    id=fs_session.id,
                                                                    report_id=report.id,
                                                                )
                                                            ),
                                                            hx_confirm="Dismiss this report?",
                                                        ):
                                                            text("Dismiss")
                                                        with button(
                                                            variant="error",
                                                            size="xs",
                                                            hx_post=str(
                                                                request.url_for(
                                                                    "file_sharing:action_report",
                                                                    id=fs_session.id,
                                                                    report_id=report.id,
                                                                )
                                                            ),
                                                            hx_confirm="Take action on this report? The session will be destroyed.",
                                                        ):
                                                            text("Action")
                                                else:
                                                    with tag.span(
                                                        classes="text-gray-400"
                                                    ):
                                                        text("--")


# ── Moderation/Reports ──


@router.post("/{id}/force-expire", name="file_sharing:force_expire")
async def force_expire(
    request: Request,
    id: UUID4,
    session: AsyncSession = Depends(get_db_session),
) -> Any:
    repo = FileShareSessionRepository.from_session(session)
    fs_session = await repo.get_by_id(id)
    if fs_session is None:
        raise HTTPException(status_code=404)

    if fs_session.status not in (
        FileShareSessionStatus.created,
        FileShareSessionStatus.active,
    ):
        await add_toast(
            request, "Session cannot be expired in its current state.", "error"
        )
        return HXRedirectResponse(
            request, str(request.url_for("file_sharing:detail", id=id)), 303
        )

    await repo.update(
        fs_session,
        update_dict={
            "status": FileShareSessionStatus.expired,
            "completed_at": now_utc(),
        },
        flush=True,
    )
    await add_toast(request, "Session has been force-expired.", "success")
    return HXRedirectResponse(
        request, str(request.url_for("file_sharing:detail", id=id)), 303
    )


@router.post("/{id}/force-destroy", name="file_sharing:force_destroy")
async def force_destroy(
    request: Request,
    id: UUID4,
    session: AsyncSession = Depends(get_db_session),
) -> Any:
    repo = FileShareSessionRepository.from_session(session)
    fs_session = await repo.get_by_id(id)
    if fs_session is None:
        raise HTTPException(status_code=404)

    if fs_session.status == FileShareSessionStatus.destroyed:
        await add_toast(request, "Session is already destroyed.", "error")
        return HXRedirectResponse(
            request, str(request.url_for("file_sharing:detail", id=id)), 303
        )

    await repo.update(
        fs_session,
        update_dict={
            "status": FileShareSessionStatus.destroyed,
            "completed_at": now_utc(),
        },
        flush=True,
    )
    await add_toast(request, "Session has been destroyed.", "success")
    return HXRedirectResponse(
        request, str(request.url_for("file_sharing:detail", id=id)), 303
    )


@router.post("/{id}/reports/{report_id}/review", name="file_sharing:review_report")
async def review_report(
    request: Request,
    id: UUID4,
    report_id: UUID4,
    session: AsyncSession = Depends(get_db_session),
) -> Any:
    report_repo = FileShareReportRepository.from_session(session)
    report = await report_repo.get_by_id(report_id)
    if report is None:
        raise HTTPException(status_code=404)

    await report_repo.update(
        report,
        update_dict={
            "status": FileShareReportStatus.reviewed,
            "reviewed_at": now_utc(),
        },
        flush=True,
    )
    await add_toast(request, "Report marked as reviewed.", "success")
    return HXRedirectResponse(
        request, str(request.url_for("file_sharing:detail", id=id)), 303
    )


@router.post("/{id}/reports/{report_id}/dismiss", name="file_sharing:dismiss_report")
async def dismiss_report(
    request: Request,
    id: UUID4,
    report_id: UUID4,
    session: AsyncSession = Depends(get_db_session),
) -> Any:
    report_repo = FileShareReportRepository.from_session(session)
    report = await report_repo.get_by_id(report_id)
    if report is None:
        raise HTTPException(status_code=404)

    await report_repo.update(
        report,
        update_dict={
            "status": FileShareReportStatus.dismissed,
            "reviewed_at": now_utc(),
        },
        flush=True,
    )
    await add_toast(request, "Report dismissed.", "success")
    return HXRedirectResponse(
        request, str(request.url_for("file_sharing:detail", id=id)), 303
    )


@router.post("/{id}/reports/{report_id}/action", name="file_sharing:action_report")
async def action_report(
    request: Request,
    id: UUID4,
    report_id: UUID4,
    session: AsyncSession = Depends(get_db_session),
) -> Any:
    report_repo = FileShareReportRepository.from_session(session)
    report = await report_repo.get_by_id(report_id)
    if report is None:
        raise HTTPException(status_code=404)

    # Mark report as actioned
    await report_repo.update(
        report,
        update_dict={
            "status": FileShareReportStatus.actioned,
            "reviewed_at": now_utc(),
        },
        flush=True,
    )

    # Also destroy the session
    session_repo = FileShareSessionRepository.from_session(session)
    fs_session = await session_repo.get_by_id(id)
    if fs_session is not None and fs_session.status != FileShareSessionStatus.destroyed:
        await session_repo.update(
            fs_session,
            update_dict={
                "status": FileShareSessionStatus.destroyed,
                "completed_at": now_utc(),
            },
            flush=True,
        )

    await add_toast(request, "Report actioned and session destroyed.", "success")
    return HXRedirectResponse(
        request, str(request.url_for("file_sharing:detail", id=id)), 303
    )


def _detail_field(label: str, value: str) -> None:
    """Render a label-value pair for the detail view."""
    with tag.div():
        with tag.dt(classes="text-sm font-medium text-gray-500"):
            text(label)
        with tag.dd(classes="mt-1 text-sm"):
            text(value)
