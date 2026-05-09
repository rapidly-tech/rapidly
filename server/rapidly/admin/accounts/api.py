"""Admin panel Stripe Connect account management (HTMX).

Server-rendered views for inspecting Stripe Connect accounts,
identity verification status, and performing account deletion.
"""

from collections.abc import Generator
from typing import Any

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from pydantic import UUID4
from tagflow import tag, text

from rapidly.billing.account import actions as account_service
from rapidly.billing.account.queries import AccountRepository
from rapidly.integrations.stripe import actions as stripe
from rapidly.models import User
from rapidly.platform.user.ordering import UserSortProperty
from rapidly.postgres import AsyncSession, get_db_session

from ..components import (
    button,
    datatable,
    description_list,
    identity_verification_status_badge,
    modal,
)
from ..toast import add_toast

router = APIRouter()


# ---------------------------------------------------------------------------
# Datatable column helpers
# ---------------------------------------------------------------------------


class IdentityVerificationStatusColumn(
    datatable.DatatableAttrColumn[User, UserSortProperty]
):
    def render(self, request: Request, item: User) -> Generator[None] | None:
        with identity_verification_status_badge(item.identity_verification_status):
            pass
        return None


class IdentityVerificationStatusDescriptionListItem(
    description_list.DescriptionListItem[User]
):
    def render(self, request: Request, item: User) -> Generator[None] | None:
        verification_status = item.identity_verification_status
        verification_id = item.identity_verification_id
        if verification_id is not None:
            stripe_url = (
                f"https://dashboard.stripe.com/identity/verification-sessions/"
                f"{verification_id}"
            )
            with tag.a(
                href=stripe_url,
                classes="link flex flex-row gap-1",
                target="_blank",
                rel="noopener noreferrer",
            ):
                text(verification_status.get_display_name())
                with tag.div(classes="icon-external-link"):
                    pass
        else:
            text(verification_status.get_display_name())
        return None


# ---------------------------------------------------------------------------
# Stripe account deletion
# ---------------------------------------------------------------------------


@router.api_route(
    "/{id}/delete-stripe", name="accounts:delete-stripe", methods=["GET", "POST"]
)
async def delete_stripe(
    request: Request,
    id: UUID4,
    stripe_account_id: str | None = Form(None),
    session: AsyncSession = Depends(get_db_session),
) -> Any:
    repo = AccountRepository.from_session(session)
    account = await repo.get_by_id(id)

    if account is None:
        raise HTTPException(status_code=404)
    if not account.stripe_id:
        raise HTTPException(status_code=400, detail="Account has no Stripe ID")

    if request.method == "POST":
        if stripe_account_id != account.stripe_id:
            await add_toast(
                request, "You entered the Stripe Account ID incorrectly", "error"
            )
            return

        if not await stripe.account_exists(account.stripe_id):
            await add_toast(
                request,
                f"Stripe Account ID {account.stripe_id} doesn't exist",
                "error",
            )
            return

        await account_service.delete_stripe_account(session, account)

        await add_toast(
            request,
            f"Stripe Connect account with ID {stripe_account_id} has been deleted",
            "success",
        )

        return

    # Render confirmation modal
    with modal(f"Delete Stripe Connect account {account.id}", open=True):
        with tag.div(classes="flex flex-col gap-4"):
            with tag.form(hx_post=str(request.url), hx_target="#modal"):
                with tag.p():
                    with tag.span():
                        text(
                            f"Are you sure you want to delete this Stripe Connect account? "
                            f"Write in {account.stripe_id} below to confirm:"
                        )
                with tag.input(
                    type="text",
                    classes="input",
                    name="stripe_account_id",
                    placeholder=f"{account.stripe_id}",
                ):
                    pass
                with tag.div(classes="modal-action"):
                    with tag.form(method="dialog"):
                        with button(ghost=True):
                            text("Cancel")
                    with tag.input(
                        type="submit", classes="btn btn-primary", value="Delete"
                    ):
                        pass
