"""
Workspaces V2 - Redesigned admin panel interface with improved UX.

This module provides a modern, three-column layout with:
- Enhanced list view with status tabs and smart grouping
- Progressive disclosure in detail views
- Contextual actions based on workspace status
- Keyboard shortcuts and accessibility improvements
"""

import re

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import UUID4, ValidationError
from pydantic_core import PydanticCustomError
from tagflow import tag, text

from rapidly.admin.workspaces.analytics import (
    PaymentAnalyticsService,
    WorkspaceSetupAnalyticsService,
)
from rapidly.admin.workspaces.forms import (
    DeleteStripeAccountForm,
    DisconnectStripeAccountForm,
    UpdateWorkspaceBasicForm,
    UpdateWorkspaceDetailsForm,
    UpdateWorkspaceInternalNotesForm,
    UpdateWorkspaceSocialsForm,
)
from rapidly.billing.account import actions as account_service
from rapidly.catalog.file.ordering import FileSortProperty
from rapidly.catalog.file.queries import FileRepository
from rapidly.core.ordering import Sorting
from rapidly.enums import AccountType
from rapidly.identity.auth import actions as auth_service
from rapidly.identity.auth.scope import Scope
from rapidly.models.file import FileServiceTypes
from rapidly.models.workspace import WorkspaceStatus
from rapidly.platform.workspace import actions as workspace_service
from rapidly.platform.workspace.queries import WorkspaceRepository
from rapidly.platform.workspace.types import WorkspaceFeatureSettings
from rapidly.postgres import (
    AsyncReadSession,
    AsyncSession,
    get_db_read_session,
    get_db_session,
)

from ..components import button, modal
from ..layout import layout
from ..responses import HXRedirectResponse
from .queries import AdminWorkspaceRepository
from .views.detail_view import WorkspaceDetailView
from .views.list_view import WorkspaceListView
from .views.modals import DeleteStripeModal, DisconnectStripeModal
from .views.sections.account_section import AccountSection
from .views.sections.files_section import FilesSection
from .views.sections.overview_section import OverviewSection
from .views.sections.settings_section import SettingsSection
from .views.sections.team_section import TeamSection

router = APIRouter(prefix="/workspaces-v2", tags=["workspaces-v2"])

_log = structlog.get_logger(__name__)


# ── List ──


@router.get("/", name="workspaces-v2:list")
async def list_workspaces(
    request: Request,
    session: AsyncReadSession = Depends(get_db_read_session),
    status: str | None = Query(None),
    q: str | None = Query(None),
    sort: str = Query("priority"),
    direction: str = Query("asc"),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    # Advanced filters
    country: str | None = Query(""),
    risk_level: str | None = Query(""),
    days_in_status: str | None = Query(""),
    has_appeal: str | None = Query(""),
) -> None:
    """
    List workspaces with enhanced filtering and smart grouping.

    Features:
    - Status-based tabs with counts
    - "Needs Attention" smart grouping
    - Search across name, slug, email
    - Advanced filters: country, risk, transfers, payments, appeals
    - Column sorting
    """
    admin_repo = AdminWorkspaceRepository.from_session(session)
    list_view = WorkspaceListView(session)

    # Convert empty strings to None and parse numbers
    country = country if country else None
    risk_level = risk_level if risk_level else None
    has_appeal = has_appeal if has_appeal else None
    days_in_status_int = int(days_in_status) if days_in_status else None

    # Parse status filter
    status_filter: WorkspaceStatus | None = None
    if status == "active":
        status_filter = WorkspaceStatus.ACTIVE
    elif status == "denied":
        status_filter = WorkspaceStatus.DENIED
    elif status == "initial_review":
        status_filter = WorkspaceStatus.INITIAL_REVIEW
    elif status == "ongoing_review":
        status_filter = WorkspaceStatus.ONGOING_REVIEW
    elif status == "created":
        status_filter = WorkspaceStatus.CREATED
    elif status == "onboarding_started":
        status_filter = WorkspaceStatus.ONBOARDING_STARTED

    workspaces, has_more = await admin_repo.list_workspaces(
        status_filter=status_filter,
        q=q,
        country=country,
        risk_level=risk_level,
        days_in_status_int=days_in_status_int,
        has_appeal=has_appeal,
        sort=sort,
        direction=direction,
        page=page,
        limit=limit,
    )

    # Get status counts for tabs
    status_counts = await list_view.get_status_counts()

    # Get distinct countries for filter dropdown
    countries = await list_view.get_distinct_countries()

    # Check if this is an HTMX request targeting just the table
    is_htmx_table_request = request.headers.get("HX-Target") == "org-list"

    if is_htmx_table_request:
        # Only return the table content
        with list_view.render_table_only(
            request,
            workspaces,
            status_filter,
            status_counts,
            page,
            has_more,
            sort,
            direction,
        ):
            pass
    else:
        # Render full page with layout
        with layout(
            request,
            [("Workspaces V2", str(request.url))],
            "workspaces-v2:list",
        ):
            with list_view.render(
                request,
                workspaces,
                status_filter,
                status_counts,
                page,
                has_more,
                sort,
                direction,
                countries,
                country,
            ):
                pass


# ── Detail ──


@router.get("/{workspace_id}", name="workspaces-v2:detail")
async def get_workspace_detail(
    request: Request,
    workspace_id: UUID4,
    section: str = Query("overview"),
    files_page: int = Query(1, ge=1),
    files_limit: int = Query(10, ge=1, le=100),
    session: AsyncReadSession = Depends(get_db_read_session),
) -> None:
    """
    Workspace detail view with three-column layout.

    Features:
    - Left sidebar: Section navigation
    - Main content: Current section details
    - Right sidebar: Contextual actions and metadata
    """
    admin_repo = AdminWorkspaceRepository.from_session(session)
    repository = WorkspaceRepository.from_session(session)

    # Fetch workspace with relationships
    workspace = await admin_repo.get_detail(workspace_id)

    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    # Fetch members separately
    workspace.members = list(await admin_repo.get_members(workspace_id))  # type: ignore[attr-defined]

    # Create views
    detail_view = WorkspaceDetailView(workspace)

    # Fetch analytics data for overview section
    setup_data = None
    payment_stats = None
    if section == "overview":
        setup_analytics = WorkspaceSetupAnalyticsService(session)
        payment_analytics = PaymentAnalyticsService(session)

        # Get setup metrics
        webhooks_count = await setup_analytics.get_webhooks_count(workspace_id)
        api_keys_count = await setup_analytics.get_workspace_tokens_count(workspace_id)
        products_count = await setup_analytics.get_products_count(workspace_id)

        user_verified = await admin_repo.get_first_member_verification_status(
            workspace_id
        )

        (
            account_charges_enabled,
            account_payouts_enabled,
        ) = await setup_analytics.check_account_enabled(workspace)
        payment_ready = await workspace_service.is_workspace_ready_for_payment(
            session, workspace
        )

        setup_score = WorkspaceSetupAnalyticsService.calculate_setup_score(
            webhooks_count,
            api_keys_count,
            products_count,
            user_verified,
            account_charges_enabled,
            account_payouts_enabled,
        )

        setup_data = {
            "setup_score": setup_score,
            "webhooks_count": webhooks_count,
            "api_keys_count": api_keys_count,
            "products_count": products_count,
            "user_verified": user_verified,
            "account_charges_enabled": account_charges_enabled,
            "account_payouts_enabled": account_payouts_enabled,
            "payment_ready": payment_ready,
            "next_review_threshold": workspace.next_review_threshold,
            "total_transfer_sum": 0,
        }

        # Get payment metrics
        (
            payment_count,
            total_amount,
            risk_scores,
        ) = await payment_analytics.get_succeeded_payments_stats(workspace_id)

        p50_risk, p90_risk = PaymentAnalyticsService.calculate_risk_percentiles(
            risk_scores
        )

        payment_stats = {
            "payment_count": payment_count,
            "total_amount": total_amount / 100,
            "p50_risk": p50_risk,
            "p90_risk": p90_risk,
            "next_review_threshold": workspace.next_review_threshold,
            "total_transfer_sum": 0,
        }

    # Render based on section
    with layout(
        request,
        [
            ("Workspaces V2", str(request.url_for("workspaces-v2:list"))),
            (workspace.name, str(request.url)),
        ],
        "workspaces-v2:detail",
    ):
        with detail_view.render(request, section):
            # Render section content
            if section == "overview":
                overview = OverviewSection(workspace)
                with overview.render(
                    request, setup_data=setup_data, payment_stats=payment_stats
                ):
                    pass
            elif section == "team":
                # Get admin user for the workspace
                admin_user = await repository.get_admin_user(session, workspace)
                team_section = TeamSection(workspace, admin_user)
                with team_section.render(request):
                    pass
            elif section == "account":
                account_section = AccountSection(
                    workspace,
                )
                with account_section.render(request):
                    pass
            elif section == "files":
                # Fetch downloadable files from repository with pagination
                file_sorting: list[Sorting[FileSortProperty]] = [
                    (FileSortProperty.created_at, True)
                ]
                file_repository = FileRepository.from_session(session)
                files, files_count = await file_repository.paginate_by_workspace(
                    workspace.id,
                    service=FileServiceTypes.downloadable,
                    sorting=file_sorting,
                    limit=files_limit,
                    page=files_page,
                )
                files_section = FilesSection(
                    workspace,
                    files=files,
                    page=files_page,
                    limit=files_limit,
                    total_count=files_count,
                )
                with files_section.render(request):
                    pass
            elif section == "history":
                # TODO: Implement history section
                with tag.div():
                    text("History section coming soon...")
            elif section == "settings":
                settings_section = SettingsSection(workspace)
                with settings_section.render(request):
                    pass
            else:
                with tag.div():
                    text(f"Unknown section: {section}")


# ── Review Actions (Approve / Deny / Block) ──


@router.post("/{workspace_id}/approve", name="workspaces-v2:approve")
async def approve_workspace(
    request: Request,
    workspace_id: UUID4,
    threshold: int | None = Query(None),
    session: AsyncSession = Depends(get_db_session),
) -> HXRedirectResponse:
    """Approve an workspace with optional threshold."""
    repository = WorkspaceRepository.from_session(session)

    workspace = await repository.get_by_id(workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    # Use provided threshold or default to $250 in cents (max as per requirement)
    next_review_threshold = threshold if threshold else 25000

    # Approve the workspace
    await workspace_service.confirm_workspace_reviewed(
        session, workspace, next_review_threshold
    )

    return HXRedirectResponse(
        request,
        str(request.url_for("workspaces-v2:detail", workspace_id=workspace_id)),
        303,
    )


@router.api_route(
    "/{workspace_id}/deny-dialog",
    name="workspaces-v2:deny_dialog",
    methods=["GET", "POST"],
    response_model=None,
)
async def deny_dialog(
    request: Request,
    workspace_id: UUID4,
    session: AsyncSession = Depends(get_db_session),
) -> HXRedirectResponse | None:
    """Deny workspace dialog and action."""
    repository = WorkspaceRepository.from_session(session)

    workspace = await repository.get_by_id(workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    if request.method == "POST":
        # Deny the workspace
        await workspace_service.deny_workspace(session, workspace)

        return HXRedirectResponse(
            request,
            str(request.url_for("workspaces-v2:detail", workspace_id=workspace_id)),
            303,
        )

    with modal("Deny Workspace", open=True):
        with tag.div(classes="flex flex-col gap-4"):
            with tag.p(classes="font-semibold text-error"):
                text("⚠️ Warning: Payments will be blocked")

            with tag.div(classes="bg-base-200 p-4 rounded-lg"):
                with tag.p(classes="mb-2"):
                    text(
                        "Denying this workspace will prevent them from receiving payments. "
                        "This action can be reversed, but the workspace will need to be reviewed again."
                    )

            with tag.div(classes="modal-action pt-6 border-t border-base-200"):
                with tag.form(method="dialog"):
                    with button(ghost=True):
                        text("Cancel")
                with tag.form(
                    hx_post=str(
                        request.url_for(
                            "workspaces-v2:deny_dialog",
                            workspace_id=workspace_id,
                        )
                    ),
                ):
                    with button(variant="error", type="submit"):
                        text("Deny Workspace")

    return None


@router.api_route(
    "/{workspace_id}/approve-denied-dialog",
    name="workspaces-v2:approve_denied_dialog",
    methods=["GET", "POST"],
    response_model=None,
)
async def approve_denied_dialog(
    request: Request,
    workspace_id: UUID4,
    session: AsyncSession = Depends(get_db_session),
) -> HXRedirectResponse | None:
    """Approve a denied workspace dialog and action."""
    repository = WorkspaceRepository.from_session(session)

    workspace = await repository.get_by_id(workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    if request.method == "POST":
        data = await request.form()
        # Convert dollars to cents (user enters 250, we store 25000)
        raw_threshold = data.get("threshold", "250")
        threshold = int(float(str(raw_threshold)) * 100)

        # Approve the workspace
        await workspace_service.confirm_workspace_reviewed(
            session, workspace, threshold
        )

        return HXRedirectResponse(
            request,
            str(request.url_for("workspaces-v2:detail", workspace_id=workspace_id)),
            303,
        )

    with modal("Approve Denied Workspace", open=True):
        with tag.form(
            hx_post=str(
                request.url_for(
                    "workspaces-v2:approve_denied_dialog",
                    workspace_id=workspace_id,
                )
            ),
            hx_target="#modal",
            classes="flex flex-col gap-4",
        ):
            with tag.p(classes="font-semibold"):
                text("Approve this previously denied workspace")

            with tag.div(classes="bg-base-200 p-4 rounded-lg"):
                with tag.p(classes="mb-3"):
                    text(
                        "This will set the workspace to ACTIVE status and allow them to receive payments. "
                        "Make sure you've reviewed the workspace details and any appeal information."
                    )

                with tag.div(classes="form-control"):
                    with tag.label(classes="label"):
                        with tag.span(classes="label-text font-semibold"):
                            text("Next Review Threshold (in dollars)")
                    with tag.input(
                        type="number",
                        name="threshold",
                        value="250",
                        placeholder="250",
                        classes="input input-bordered",
                    ):
                        pass
                    with tag.label(classes="label"):
                        with tag.span(classes="label-text-alt"):
                            text("Amount in dollars that will trigger next review")

            with tag.div(classes="modal-action pt-6 border-t border-base-200"):
                with tag.form(method="dialog"):
                    with button(ghost=True):
                        text("Cancel")
                with button(variant="primary", type="submit"):
                    text("Approve Workspace")

    return None


@router.api_route(
    "/{workspace_id}/unblock-approve-dialog",
    name="workspaces-v2:unblock_approve_dialog",
    methods=["GET", "POST"],
    response_model=None,
)
async def unblock_approve_dialog(
    request: Request,
    workspace_id: UUID4,
    session: AsyncSession = Depends(get_db_session),
) -> HXRedirectResponse | None:
    """Unblock and approve workspace dialog and action."""
    repository = WorkspaceRepository.from_session(session)

    workspace = await repository.get_by_id(workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    if request.method == "POST":
        data = await request.form()
        # Convert dollars to cents (user enters 250, we store 25000)
        raw_threshold = data.get("threshold", "250")
        threshold = int(float(str(raw_threshold)) * 100)

        # Unblock the workspace (set blocked_at to None)
        workspace.blocked_at = None

        # Approve the workspace
        await workspace_service.confirm_workspace_reviewed(
            session, workspace, threshold
        )

        return HXRedirectResponse(
            request,
            str(request.url_for("workspaces-v2:detail", workspace_id=workspace_id)),
            303,
        )

    with modal("Unblock & Approve Workspace", open=True):
        with tag.form(
            hx_post=str(
                request.url_for(
                    "workspaces-v2:unblock_approve_dialog",
                    workspace_id=workspace_id,
                )
            ),
            hx_target="#modal",
            classes="flex flex-col gap-4",
        ):
            with tag.p(classes="font-semibold"):
                text("Unblock and approve this workspace")

            with tag.div(classes="bg-base-200 p-4 rounded-lg"):
                with tag.p(classes="mb-3"):
                    text(
                        "This will unblock the workspace and set it to ACTIVE status. "
                        "The workspace will be able to receive payments again."
                    )

                with tag.div(classes="form-control"):
                    with tag.label(classes="label"):
                        with tag.span(classes="label-text font-semibold"):
                            text("Next Review Threshold (in dollars)")
                    with tag.input(
                        type="number",
                        name="threshold",
                        value="250",
                        placeholder="250",
                        classes="input input-bordered",
                    ):
                        pass
                    with tag.label(classes="label"):
                        with tag.span(classes="label-text-alt"):
                            text("Amount in dollars that will trigger next review")

            with tag.div(classes="modal-action pt-6 border-t border-base-200"):
                with tag.form(method="dialog"):
                    with button(ghost=True):
                        text("Cancel")
                with button(variant="primary", type="submit"):
                    text("Unblock & Approve")

    return None


@router.api_route(
    "/{workspace_id}/block-dialog",
    name="workspaces-v2:block_dialog",
    methods=["GET", "POST"],
    response_model=None,
)
async def block_dialog(
    request: Request,
    workspace_id: UUID4,
    session: AsyncSession = Depends(get_db_session),
) -> HXRedirectResponse | None:
    """Block workspace dialog and action."""
    repository = WorkspaceRepository.from_session(session)

    workspace = await repository.get_by_id(workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    if request.method == "POST":
        # Block the workspace (set blocked_at to current time)
        from datetime import UTC, datetime

        workspace.blocked_at = datetime.now(UTC)

        return HXRedirectResponse(
            request,
            str(request.url_for("workspaces-v2:detail", workspace_id=workspace_id)),
            303,
        )

    with modal("Block Workspace", open=True):
        with tag.div(classes="flex flex-col gap-4"):
            with tag.p(classes="font-semibold text-error"):
                text("⚠️ Critical Warning: Complete Workspace Block")

            with tag.div(classes="bg-error/10 border border-error/20 p-4 rounded-lg"):
                with tag.p(classes="font-semibold mb-2 text-error"):
                    text("Blocking this workspace will:")
                with tag.ul(classes="list-disc list-inside space-y-1 text-sm"):
                    with tag.li():
                        text("Prevent all access to the workspace")
                    with tag.li():
                        text("Block all payments and transactions")
                    with tag.li():
                        text("Disable API access")
                    with tag.li():
                        text("Prevent any workspace operations")

                with tag.p(classes="mt-3 text-sm font-semibold"):
                    text(
                        "This is a severe action typically used for fraud or ToS violations."
                    )

            with tag.div(classes="modal-action pt-6 border-t border-base-200"):
                with tag.form(method="dialog"):
                    with button(ghost=True):
                        text("Cancel")
                with tag.form(
                    hx_post=str(
                        request.url_for(
                            "workspaces-v2:block_dialog",
                            workspace_id=workspace_id,
                        )
                    ),
                ):
                    with button(variant="error", type="submit"):
                        text("Block Workspace")

    return None


# ── Settings (Edit Workspace) ──


@router.api_route(
    "/{workspace_id}/edit",
    name="workspaces-v2:edit",
    methods=["GET", "POST"],
    response_model=None,
)
async def edit_workspace(
    request: Request,
    workspace_id: UUID4,
    session: AsyncSession = Depends(get_db_session),
) -> HXRedirectResponse | None:
    """Edit workspace details."""
    repository = WorkspaceRepository.from_session(session)

    # Fetch workspace
    workspace = await repository.get_by_id(workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    validation_error = None

    if request.method == "POST":
        data = await request.form()
        try:
            form = UpdateWorkspaceBasicForm.model_validate_form(data)
            if form.slug != workspace.slug:
                existing_slug = await repository.get_by_slug(form.slug)
                if existing_slug is not None:
                    raise ValidationError.from_exception_data(
                        title="SlugAlreadyExists",
                        line_errors=[
                            {
                                "loc": ("slug",),
                                "type": PydanticCustomError(
                                    "SlugAlreadyExists",
                                    "An workspace with this slug already exists.",
                                ),
                                "input": form.slug,
                            }
                        ],
                    )

            # Update workspace with basic fields only
            form_dict = form.model_dump(exclude_none=True)
            workspace = await repository.update(
                workspace,
                update_dict=form_dict,
            )
            redirect_url = (
                str(request.url_for("workspaces-v2:detail", workspace_id=workspace_id))
                + "?section=settings"
            )
            return HXRedirectResponse(request, redirect_url, 303)

        except ValidationError as e:
            validation_error = e

    # Prepare data for form rendering
    form_data = {
        "name": workspace.name,
        "slug": workspace.slug,
        "customer_invoice_prefix": workspace.customer_invoice_prefix,
    }

    with modal("Edit Basic Settings", open=True):
        with tag.p(classes="text-sm text-base-content/60 mb-4"):
            text("Update workspace name, slug, and customer invoice prefix")

        with UpdateWorkspaceBasicForm.render(
            data=form_data,
            validation_error=validation_error,
            hx_post=str(
                request.url_for("workspaces-v2:edit", workspace_id=workspace_id)
            ),
            hx_target="#modal",
            classes="space-y-4",
        ):
            # Action buttons
            with tag.div(classes="modal-action pt-6 border-t border-base-200"):
                with tag.form(method="dialog"):
                    with button(ghost=True):
                        text("Cancel")
                with button(
                    type="submit",
                    variant="primary",
                ):
                    text("Save Changes")

    return None


@router.api_route(
    "/{workspace_id}/edit-details",
    name="workspaces-v2:edit_details",
    methods=["GET", "POST"],
    response_model=None,
)
async def edit_details(
    request: Request,
    workspace_id: UUID4,
    session: AsyncSession = Depends(get_db_session),
) -> HXRedirectResponse | None:
    """Edit workspace details (about, share description, intended use)."""
    repository = WorkspaceRepository.from_session(session)

    # Fetch workspace
    workspace = await repository.get_by_id(workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    validation_error = None

    if request.method == "POST":
        try:
            data = await request.form()
            form = UpdateWorkspaceDetailsForm.model_validate_form(data)

            # Update workspace with form data
            form_dict = form.model_dump(exclude_none=True)
            workspace = await repository.update(
                workspace,
                update_dict=form_dict,
            )
            redirect_url = (
                str(request.url_for("workspaces-v2:detail", workspace_id=workspace_id))
                + "?section=settings"
            )
            return HXRedirectResponse(request, redirect_url, 303)

        except ValidationError as e:
            validation_error = e

    # Prepare data for form rendering
    form_data = {
        "website": workspace.website,
        "details": workspace.details or {},
    }

    with modal("Edit Workspace Details", open=True):
        with tag.p(classes="text-sm text-base-content/60 mb-4"):
            text("Update workspace details (about, share description, intended use)")

        with UpdateWorkspaceDetailsForm.render(
            data=form_data,
            validation_error=validation_error,
            hx_post=str(
                request.url_for("workspaces-v2:edit_details", workspace_id=workspace_id)
            ),
            hx_target="#modal",
            classes="space-y-4",
        ):
            # Action buttons
            with tag.div(classes="modal-action pt-6 border-t border-base-200"):
                with tag.form(method="dialog"):
                    with button(ghost=True):
                        text("Cancel")
                with button(
                    type="submit",
                    variant="primary",
                ):
                    text("Save Changes")

    return None


@router.api_route(
    "/{workspace_id}/edit-socials",
    name="workspaces-v2:edit_socials",
    methods=["GET", "POST"],
    response_model=None,
)
async def edit_socials(
    request: Request,
    workspace_id: UUID4,
    session: AsyncSession = Depends(get_db_session),
) -> HXRedirectResponse | None:
    """Edit workspace social media links."""
    # Platform name constants for consistency
    PLATFORM_YOUTUBE = "youtube"
    PLATFORM_INSTAGRAM = "instagram"
    PLATFORM_LINKEDIN = "linkedin"
    PLATFORM_X = "x"
    PLATFORM_FACEBOOK = "facebook"
    PLATFORM_THREADS = "threads"
    PLATFORM_TIKTOK = "tiktok"
    PLATFORM_GITHUB = "github"
    PLATFORM_DISCORD = "discord"
    PLATFORM_OTHER = "other"

    repository = WorkspaceRepository.from_session(session)

    workspace = await repository.get_by_id(workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    validation_error = None

    if request.method == "POST":
        try:
            data = await request.form()
            form = UpdateWorkspaceSocialsForm.model_validate_form(data)

            # Build socials list from form data
            socials: list[dict[str, str]] = []
            if form.youtube_url:
                socials.append(
                    {"platform": PLATFORM_YOUTUBE, "url": str(form.youtube_url)}
                )
            if form.instagram_url:
                socials.append(
                    {"platform": PLATFORM_INSTAGRAM, "url": str(form.instagram_url)}
                )
            if form.linkedin_url:
                socials.append(
                    {"platform": PLATFORM_LINKEDIN, "url": str(form.linkedin_url)}
                )
            if form.x_url:
                socials.append({"platform": PLATFORM_X, "url": str(form.x_url)})
            if form.facebook_url:
                socials.append(
                    {"platform": PLATFORM_FACEBOOK, "url": str(form.facebook_url)}
                )
            if form.threads_url:
                socials.append(
                    {"platform": PLATFORM_THREADS, "url": str(form.threads_url)}
                )
            if form.tiktok_url:
                socials.append(
                    {"platform": PLATFORM_TIKTOK, "url": str(form.tiktok_url)}
                )
            if form.github_url:
                socials.append(
                    {"platform": PLATFORM_GITHUB, "url": str(form.github_url)}
                )
            if form.discord_url:
                socials.append(
                    {"platform": PLATFORM_DISCORD, "url": str(form.discord_url)}
                )
            if form.other_url:
                socials.append({"platform": PLATFORM_OTHER, "url": str(form.other_url)})

            # Update workspace with new socials
            workspace = await repository.update(
                workspace,
                update_dict={"socials": socials},
            )
            redirect_url = (
                str(request.url_for("workspaces-v2:detail", workspace_id=workspace_id))
                + "?section=settings"
            )
            return HXRedirectResponse(request, redirect_url, 303)

        except ValidationError as e:
            validation_error = e

    # Prepare data for form rendering - extract URLs from existing socials
    existing_socials = workspace.socials or []
    form_data: dict[str, str | None] = {
        "youtube_url": None,
        "instagram_url": None,
        "linkedin_url": None,
        "x_url": None,
        "facebook_url": None,
        "threads_url": None,
        "tiktok_url": None,
        "github_url": None,
        "discord_url": None,
        "other_url": None,
    }
    for social in existing_socials:
        platform = social.get("platform", "").lower()
        url = social.get("url", "")
        if platform == PLATFORM_YOUTUBE:
            form_data["youtube_url"] = url
        elif platform == PLATFORM_INSTAGRAM:
            form_data["instagram_url"] = url
        elif platform == PLATFORM_LINKEDIN:
            form_data["linkedin_url"] = url
        elif platform == PLATFORM_X:
            form_data["x_url"] = url
        elif platform == PLATFORM_FACEBOOK:
            form_data["facebook_url"] = url
        elif platform == PLATFORM_THREADS:
            form_data["threads_url"] = url
        elif platform == PLATFORM_TIKTOK:
            form_data["tiktok_url"] = url
        elif platform == PLATFORM_GITHUB:
            form_data["github_url"] = url
        elif platform == PLATFORM_DISCORD:
            form_data["discord_url"] = url
        elif platform == PLATFORM_OTHER:
            form_data["other_url"] = url

    with modal("Edit Social Media Links", open=True):
        with tag.p(classes="text-sm text-base-content/60 mb-4"):
            text("Update workspace social media links for creator outreach")

        with UpdateWorkspaceSocialsForm.render(
            data=form_data,
            validation_error=validation_error,
            hx_post=str(
                request.url_for("workspaces-v2:edit_socials", workspace_id=workspace_id)
            ),
            hx_target="#modal",
            classes="space-y-4",
        ):
            # Action buttons
            with tag.div(classes="modal-action pt-6 border-t border-base-200"):
                with tag.form(method="dialog"):
                    with button(ghost=True):
                        text("Cancel")
                with button(
                    type="submit",
                    variant="primary",
                ):
                    text("Save Changes")

    return None


@router.api_route(
    "/{workspace_id}/edit-features",
    name="workspaces-v2:edit_features",
    methods=["GET", "POST"],
    response_model=None,
)
async def edit_features(
    request: Request,
    workspace_id: UUID4,
    session: AsyncSession = Depends(get_db_session),
) -> HXRedirectResponse | None:
    """Edit workspace feature flags."""
    repository = WorkspaceRepository.from_session(session)

    # Fetch workspace
    workspace = await repository.get_by_id(workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    if request.method == "POST":
        try:
            data = await request.form()

            # Parse feature flags from form data
            feature_flags = {}
            for field_name in WorkspaceFeatureSettings.model_fields.keys():
                # Checkboxes that are unchecked won't be in form data
                feature_flags[field_name] = field_name in data

            # Merge with existing feature_settings
            updated_feature_settings = {
                **workspace.feature_settings,
                **feature_flags,
            }

            # Update workspace
            workspace = await repository.update(
                workspace,
                update_dict={"feature_settings": updated_feature_settings},
            )
            redirect_url = (
                str(request.url_for("workspaces-v2:detail", workspace_id=workspace_id))
                + "?section=settings"
            )
            return HXRedirectResponse(request, redirect_url, 303)

        except ValidationError:
            pass

    # Render feature flags form
    with modal("Edit Feature Flags", open=True):
        with tag.p(classes="text-sm text-base-content/60 mb-4"):
            text("Enable or disable feature flags for this workspace")

        with tag.form(
            hx_post=str(
                request.url_for(
                    "workspaces-v2:edit_features", workspace_id=workspace_id
                )
            ),
            hx_target="#modal",
            classes="space-y-4",
        ):
            # Feature flags checkboxes
            with tag.div(classes="space-y-3"):
                for (
                    field_name,
                    field_info,
                ) in WorkspaceFeatureSettings.model_fields.items():
                    enabled = workspace.feature_settings.get(field_name, False)
                    label = field_name.replace("_", " ").title()

                    with tag.div(classes="form-control"):
                        with tag.label(
                            classes="label cursor-pointer justify-start gap-3"
                        ):
                            with tag.input(
                                type="checkbox",
                                name=field_name,
                                classes="checkbox checkbox-sm",
                                **{"checked": ""} if enabled else {},
                            ):
                                pass
                            with tag.span(classes="label-text"):
                                text(label)

            # Action buttons
            with tag.div(classes="modal-action pt-6 border-t border-base-200"):
                with tag.form(method="dialog"):
                    with button(ghost=True):
                        text("Cancel")
                with button(
                    type="submit",
                    variant="primary",
                ):
                    text("Save Changes")

    return None


# ── Internal Notes ──


@router.api_route(
    "/{workspace_id}/add-note",
    name="workspaces-v2:add_note",
    methods=["GET", "POST"],
    response_model=None,
)
async def add_note(
    request: Request,
    workspace_id: UUID4,
    session: AsyncSession = Depends(get_db_session),
) -> HXRedirectResponse | None:
    """Add internal notes to an workspace."""
    repository = WorkspaceRepository.from_session(session)

    # Fetch workspace
    workspace = await repository.get_by_id(workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    validation_error = None

    if request.method == "POST":
        try:
            data = await request.form()
            form = UpdateWorkspaceInternalNotesForm.model_validate_form(data)
            workspace = await repository.update(
                workspace, update_dict=form.model_dump(exclude_none=True)
            )
            return HXRedirectResponse(
                request,
                str(request.url_for("workspaces-v2:detail", workspace_id=workspace_id)),
                303,
            )

        except ValidationError as e:
            validation_error = e

    with modal("Add Internal Notes", open=True):
        with tag.p(classes="text-sm text-base-content/60 mb-4"):
            text("Add internal notes about this workspace (admin only)")

        with UpdateWorkspaceInternalNotesForm.render(
            data=workspace,
            validation_error=validation_error,
            hx_post=str(
                request.url_for("workspaces-v2:add_note", workspace_id=workspace_id)
            ),
            hx_target="#modal",
            classes="space-y-4",
        ):
            # Action buttons
            with tag.div(classes="modal-action pt-6 border-t border-base-200"):
                with tag.form(method="dialog"):
                    with button(ghost=True):
                        text("Cancel")
                with button(
                    type="submit",
                    variant="primary",
                ):
                    text("Save Notes")

    return None


@router.api_route(
    "/{workspace_id}/edit-note",
    name="workspaces-v2:edit_note",
    methods=["GET", "POST"],
    response_model=None,
)
async def edit_note(
    request: Request,
    workspace_id: UUID4,
    session: AsyncSession = Depends(get_db_session),
) -> HXRedirectResponse | None:
    """Edit internal notes for an workspace."""
    repository = WorkspaceRepository.from_session(session)

    # Fetch workspace
    workspace = await repository.get_by_id(workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    validation_error = None

    if request.method == "POST":
        try:
            data = await request.form()
            form = UpdateWorkspaceInternalNotesForm.model_validate_form(data)
            workspace = await repository.update(
                workspace, update_dict=form.model_dump(exclude_none=True)
            )
            return HXRedirectResponse(
                request,
                str(request.url_for("workspaces-v2:detail", workspace_id=workspace_id)),
                303,
            )

        except ValidationError as e:
            validation_error = e

    with modal("Edit Internal Notes", open=True):
        with tag.p(classes="text-sm text-base-content/60 mb-4"):
            text("Update internal notes about this workspace (admin only)")

        with UpdateWorkspaceInternalNotesForm.render(
            data=workspace,
            validation_error=validation_error,
            hx_post=str(
                request.url_for("workspaces-v2:edit_note", workspace_id=workspace_id)
            ),
            hx_target="#modal",
            classes="space-y-4",
        ):
            # Action buttons
            with tag.div(classes="modal-action pt-6 border-t border-base-200"):
                with tag.form(method="dialog"):
                    with button(ghost=True):
                        text("Cancel")
                with button(
                    type="submit",
                    variant="primary",
                ):
                    text("Save Notes")

    return None


# ── Team Management (Impersonate / Admin / Members) ──


@router.get(
    "/{workspace_id}/impersonate/{user_id}",
    name="workspaces-v2:impersonate",
)
async def impersonate_user(
    request: Request,
    workspace_id: UUID4,
    user_id: UUID4,
    session: AsyncSession = Depends(get_db_session),
) -> HXRedirectResponse:
    """Impersonate a user by creating a read-only session for them."""
    from datetime import timedelta

    from rapidly.config import settings

    admin_repo = AdminWorkspaceRepository.from_session(session)

    # Fetch the user to impersonate
    user = await admin_repo.get_user_by_id(user_id)

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Verify user belongs to workspace
    membership = await admin_repo.get_membership(user_id, workspace_id)
    if not membership:
        raise HTTPException(
            status_code=400, detail="User is not a member of this workspace"
        )

    # Create read-only impersonation session with time limit
    token, impersonation_session = await auth_service._create_user_session(
        session=session,
        user=user,
        user_agent=request.headers.get("User-Agent", ""),
        scopes=[Scope.web_read],  # Read-only
        expire_in=timedelta(minutes=60),  # Time-limited
    )

    # Get user's first workspace for redirect
    repository = WorkspaceRepository.from_session(session)
    user_orgs = await repository.get_all_by_user(user.id)
    slug = user_orgs[0].slug if user_orgs else ""
    # Guard against protocol-relative redirect (e.g. slug="//evil.com")
    from urllib.parse import urlparse as _urlparse

    redirect_url = f"/{slug}" if slug and not _urlparse(f"/{slug}").netloc else "/"

    response = HXRedirectResponse(request, redirect_url, 303)

    # Get current admin session token and validate it is safe to echo back
    _safe_cookie_re = re.compile(r"^[A-Za-z0-9_\-=.]+$")
    current_token = request.cookies.get(settings.USER_SESSION_COOKIE_KEY)

    # Preserve admin session in impersonation cookie.
    # Sanitize: strip control characters to prevent cookie header injection.
    if current_token:
        sanitized_token = re.sub(r"[\x00-\x1f\x7f]", "", current_token)
        response.set_cookie(
            settings.IMPERSONATION_COOKIE_KEY,
            value=sanitized_token,
            expires=impersonation_session.expires_at,
            path="/",
            domain=settings.USER_SESSION_COOKIE_DOMAIN,
            secure=request.url.hostname not in ["127.0.0.1", "localhost"],
            httponly=True,
            samesite="lax",
        )

    # Set impersonated session cookie
    auth_service._set_session_cookie(
        request, response, token, impersonation_session.expires_at
    )

    # Set impersonation indicator (JS-readable for UI)
    response.set_cookie(
        settings.IMPERSONATION_INDICATOR_COOKIE_KEY,
        value="true",
        expires=impersonation_session.expires_at,
        path="/",
        domain=settings.USER_SESSION_COOKIE_DOMAIN,
        secure=request.url.hostname not in ["127.0.0.1", "localhost"],
        httponly=False,  # JS-readable for UI banner
        samesite="lax",
    )

    return response


@router.post(
    "/{workspace_id}/make-admin/{user_id}",
    name="workspaces-v2:make_admin",
)
async def make_admin(
    request: Request,
    workspace_id: UUID4,
    user_id: UUID4,
    session: AsyncSession = Depends(get_db_session),
) -> HXRedirectResponse:
    """Make a user an admin of the workspace."""
    repository = WorkspaceRepository.from_session(session)

    workspace = await repository.get_by_id(workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    # Change the admin user
    try:
        from rapidly.billing.account import actions as account_service

        if not workspace.account:
            raise HTTPException(status_code=400, detail="Workspace has no account")

        await account_service.change_admin(
            session, workspace.account, user_id, workspace_id
        )
    except Exception as e:
        _log.error("Failed to make user admin", error=str(e))
        raise HTTPException(status_code=400, detail=str(e))

    redirect_url = (
        str(request.url_for("workspaces-v2:detail", workspace_id=workspace_id))
        + "?section=team"
    )
    return HXRedirectResponse(request, redirect_url, 303)


@router.delete(
    "/{workspace_id}/remove-member/{user_id}",
    name="workspaces-v2:remove_member",
)
async def remove_member(
    request: Request,
    workspace_id: UUID4,
    user_id: UUID4,
    session: AsyncSession = Depends(get_db_session),
) -> HXRedirectResponse:
    """Remove a member from the workspace."""
    repository = WorkspaceRepository.from_session(session)

    workspace = await repository.get_by_id(workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    # Remove the user from the workspace
    try:
        from rapidly.platform.workspace_membership import (
            actions as workspace_membership_service,
        )

        await workspace_membership_service.remove_member(session, workspace.id, user_id)
    except Exception as e:
        _log.error("Failed to remove member", error=str(e))
        raise HTTPException(status_code=400, detail=str(e))

    redirect_url = (
        str(request.url_for("workspaces-v2:detail", workspace_id=workspace_id))
        + "?section=team"
    )
    return HXRedirectResponse(request, redirect_url, 303)


# ── Danger Zone (Delete Workspace) ──


@router.api_route(
    "/{workspace_id}/delete-dialog",
    name="workspaces-v2:delete_dialog",
    methods=["GET", "POST"],
    response_model=None,
)
async def delete_dialog(
    request: Request,
    workspace_id: UUID4,
    session: AsyncSession = Depends(get_db_session),
) -> HXRedirectResponse | None:
    """Delete workspace dialog and action."""
    repository = WorkspaceRepository.from_session(session)

    workspace = await repository.get_by_id(workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    if request.method == "POST":
        await workspace_service.delete(session, workspace)

        return HXRedirectResponse(
            request,
            str(request.url_for("workspaces-v2:list")),
            303,
        )

    with modal(f"Delete Workspace {workspace.name}", open=True):
        with tag.div(classes="flex flex-col gap-4"):
            with tag.p(classes="font-semibold text-error"):
                text("Are you sure you want to delete this workspace?")

            with tag.div(classes="bg-base-200 p-4 rounded-lg"):
                with tag.p(classes="font-semibold mb-2"):
                    text("Deleting this workspace DOES NOT:")
                with tag.ul(classes="list-disc list-inside space-y-1 text-sm"):
                    with tag.li():
                        text("Delete or anonymize users")
                    with tag.li():
                        text("Delete or anonymize the account")
                    with tag.li():
                        text("Delete customers or products")
                    with tag.li():
                        text("Remove API tokens")

            with tag.div(classes="modal-action pt-6 border-t border-base-200"):
                with tag.form(method="dialog"):
                    with button(ghost=True):
                        text("Cancel")
                with tag.form(
                    hx_post=str(
                        request.url_for(
                            "workspaces-v2:delete_dialog",
                            workspace_id=workspace_id,
                        )
                    ),
                ):
                    with button(variant="error", type="submit"):
                        text("Delete Workspace")

    return None


# ── Stripe Account Management ──


@router.api_route(
    "/{workspace_id}/setup-account",
    name="workspaces-v2:setup_account",
    methods=["GET", "POST"],
    response_model=None,
)
async def setup_account(
    request: Request,
    workspace_id: UUID4,
    session: AsyncSession = Depends(get_db_session),
) -> HXRedirectResponse | None:
    """Show modal to setup a manual payment account."""
    repository = WorkspaceRepository.from_session(session)

    workspace = await repository.get_by_id(workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    if request.method == "POST":
        # TODO: Implement manual account creation
        # This would need to create an Account record and associate it with the workspace
        raise HTTPException(
            status_code=501, detail="Manual account creation not yet implemented"
        )

    # GET - Show modal
    with modal("Setup Manual Account", open=True):
        with tag.div(classes="space-y-4"):
            with tag.p(classes="text-sm text-base-content/60"):
                text("This will create a manual payment account for this workspace.")

            with tag.div(classes="alert alert-warning"):
                with tag.span(classes="text-sm"):
                    text(
                        "Manual accounts require manual payout processing and do not integrate with Stripe."
                    )

            # Action buttons
            with tag.div(classes="modal-action pt-6 border-t border-base-200"):
                with tag.form(method="dialog"):
                    with button(ghost=True):
                        text("Cancel")
                with button(
                    variant="primary",
                    hx_post=str(
                        request.url_for(
                            "workspaces-v2:setup_account",
                            workspace_id=workspace_id,
                        )
                    ),
                ):
                    text("Create Manual Account")

    return None


@router.api_route(
    "/{workspace_id}/disconnect-stripe-account",
    name="workspaces-v2:disconnect_stripe_account",
    methods=["GET", "POST"],
    response_model=None,
)
async def disconnect_stripe_account(
    request: Request,
    workspace_id: UUID4,
    session: AsyncSession = Depends(get_db_session),
) -> HXRedirectResponse | None:
    repository = WorkspaceRepository.from_session(session)
    workspace = await repository.get_by_id_with_account(workspace_id)

    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    if not workspace.account:
        raise HTTPException(status_code=400, detail="Workspace has no account")

    if workspace.account.account_type != AccountType.stripe:
        raise HTTPException(status_code=400, detail="Account is not a Stripe account")

    if not workspace.account.stripe_id:
        raise HTTPException(status_code=400, detail="Account does not have a Stripe ID")

    account = workspace.account
    validation_error = None

    if request.method == "POST":
        data = await request.form()
        try:
            form = DisconnectStripeAccountForm.model_validate_form(data)

            if form.stripe_account_id != account.stripe_id:
                raise ValidationError.from_exception_data(
                    title="StripeAccountIdMismatch",
                    line_errors=[
                        {
                            "loc": ("stripe_account_id",),
                            "type": PydanticCustomError(
                                "StripeAccountIdMismatch",
                                "Stripe Account ID does not match.",
                            ),
                            "input": form.stripe_account_id,
                        }
                    ],
                )

            old_stripe_id = account.stripe_id
            archive_account = await account_service.disconnect_stripe(session, account)

            admin_repo = AdminWorkspaceRepository.from_session(session)
            disconnect_note = (
                f"Stripe account disconnected.\n"
                f"Previous Stripe ID: {old_stripe_id}\n"
                f"Archive Account ID: {archive_account.id}\n"
                f"Reason: {form.reason.strip()}"
            )
            await admin_repo.append_internal_note(workspace, disconnect_note)

            is_ready = await workspace_service.is_workspace_ready_for_payment(
                session, workspace
            )

            _log.info(
                "Stripe account disconnected from workspace",
                workspace_id=str(workspace_id),
                old_stripe_id=old_stripe_id,
                archive_account_id=str(archive_account.id),
                payment_ready=is_ready,
            )

            redirect_url = (
                str(request.url_for("workspaces-v2:detail", workspace_id=workspace_id))
                + "?section=account"
            )
            return HXRedirectResponse(request, redirect_url, 303)

        except ValidationError as e:
            validation_error = e

    form_action = str(
        request.url_for(
            "workspaces-v2:disconnect_stripe_account",
            workspace_id=workspace_id,
        )
    )
    modal_view = DisconnectStripeModal(account, form_action, validation_error)
    with modal_view.render():
        pass

    return None


@router.api_route(
    "/{workspace_id}/delete-stripe-account",
    name="workspaces-v2:delete_stripe_account",
    methods=["GET", "POST"],
    response_model=None,
)
async def delete_stripe_account(
    request: Request,
    workspace_id: UUID4,
    session: AsyncSession = Depends(get_db_session),
) -> HXRedirectResponse | None:
    repository = WorkspaceRepository.from_session(session)
    workspace = await repository.get_by_id_with_account(workspace_id)

    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    if not workspace.account:
        raise HTTPException(status_code=400, detail="Workspace has no account")

    if workspace.account.account_type != AccountType.stripe:
        raise HTTPException(status_code=400, detail="Account is not a Stripe account")

    if not workspace.account.stripe_id:
        raise HTTPException(status_code=400, detail="Account does not have a Stripe ID")

    account = workspace.account
    validation_error = None

    if request.method == "POST":
        data = await request.form()
        try:
            form = DeleteStripeAccountForm.model_validate_form(data)

            if form.stripe_account_id != account.stripe_id:
                raise ValidationError.from_exception_data(
                    title="StripeAccountIdMismatch",
                    line_errors=[
                        {
                            "loc": ("stripe_account_id",),
                            "type": PydanticCustomError(
                                "StripeAccountIdMismatch",
                                "Stripe Account ID does not match.",
                            ),
                            "input": form.stripe_account_id,
                        }
                    ],
                )

            old_stripe_id = account.stripe_id
            await account_service.delete_stripe_account(session, account)

            admin_repo = AdminWorkspaceRepository.from_session(session)
            delete_note = (
                f"Stripe account deleted.\n"
                f"Deleted Stripe ID: {old_stripe_id}\n"
                f"Reason: {form.reason.strip()}"
            )
            await admin_repo.append_internal_note(workspace, delete_note)

            _log.info(
                "Stripe account deleted from workspace",
                workspace_id=str(workspace_id),
                deleted_stripe_id=old_stripe_id,
            )

            redirect_url = (
                str(request.url_for("workspaces-v2:detail", workspace_id=workspace_id))
                + "?section=account"
            )
            return HXRedirectResponse(request, redirect_url, 303)

        except ValidationError as e:
            validation_error = e

    form_action = str(
        request.url_for(
            "workspaces-v2:delete_stripe_account",
            workspace_id=workspace_id,
        )
    )
    modal_view = DeleteStripeModal(account, form_action, validation_error)
    with modal_view.render():
        pass

    return None


__all__ = ["router"]
