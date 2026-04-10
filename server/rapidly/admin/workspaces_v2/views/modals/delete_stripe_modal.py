"""Stripe account deletion confirmation modal.

Renders a confirmation dialog that requires the admin to acknowledge
the irreversible nature of deleting a Stripe Connect account.
"""

import contextlib
from collections.abc import Generator

from pydantic import ValidationError
from tagflow import tag, text

from rapidly.admin.components import button, modal
from rapidly.admin.workspaces.forms import DeleteStripeAccountForm
from rapidly.models import Account

_EMPTY_FORM: dict[str, str] = {"stripe_account_id": "", "reason": ""}

_WARNING_TEXT = (
    "This action will delete the Stripe Connect account on Stripe's side "
    "and clear all capability flags. This cannot be undone."
)


class DeleteStripeModal:
    def __init__(
        self,
        account: Account,
        form_action: str,
        validation_error: ValidationError | None = None,
    ):
        self._account = account
        self._action = form_action
        self._error = validation_error

    @contextlib.contextmanager
    def render(self) -> Generator[None]:
        with modal("Delete Stripe Account", open=True):
            with tag.div(classes="flex flex-col gap-4"):
                with tag.p(classes="font-semibold text-error"):
                    text("This will permanently delete the Stripe Connect account")

                with tag.div(classes="bg-base-200 p-4 rounded-lg"):
                    with tag.p(classes="mb-2"):
                        text(_WARNING_TEXT)
                    with tag.p(classes="text-sm text-base-content/60"):
                        text(f"Stripe Account ID: {self._account.stripe_id}")

                with DeleteStripeAccountForm.render(
                    data=_EMPTY_FORM,
                    validation_error=self._error,
                    hx_post=self._action,
                    hx_target="#modal",
                    classes="space-y-4",
                ):
                    with tag.div(classes="modal-action pt-6 border-t border-base-200"):
                        with tag.form(method="dialog"):
                            with button(ghost=True):
                                text("Cancel")
                        with button(type="submit", variant="error"):
                            text("Delete Stripe Account")

        yield


__all__ = ["DeleteStripeModal"]
