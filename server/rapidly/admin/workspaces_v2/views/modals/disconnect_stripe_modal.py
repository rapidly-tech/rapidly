"""Stripe account disconnection confirmation modal.

Unlike deletion, disconnecting only removes the link between the
workspace and the Stripe account -- the Stripe account itself survives.
"""

import contextlib
from collections.abc import Generator

from pydantic import ValidationError
from tagflow import tag, text

from rapidly.admin.components import button, modal
from rapidly.admin.workspaces.forms import DisconnectStripeAccountForm
from rapidly.models import Account

_EMPTY_FORM: dict[str, str] = {"stripe_account_id": "", "reason": ""}

_EXPLANATION = (
    "The Stripe connection will be removed, but the Stripe Account will "
    "remain and the user can access it. Use it on cases where the "
    "Stripe Account cannot be deleted."
)


class DisconnectStripeModal:
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
        with modal("Disconnect Stripe Account", open=True):
            with tag.div(classes="flex flex-col gap-4"):
                with tag.p(classes="font-semibold text-warning"):
                    text("This will unlink the Stripe account from this workspace.")

                with tag.div(classes="bg-base-200 p-4 rounded-lg"):
                    with tag.p(classes="mb-2"):
                        text(_EXPLANATION)
                    with tag.p(classes="text-sm text-base-content/60"):
                        text(f"Current Stripe Account ID: {self._account.stripe_id}")

                with DisconnectStripeAccountForm.render(
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
                        with button(type="submit", variant="warning"):
                            text("Disconnect Stripe Account")

        yield


__all__ = ["DisconnectStripeModal"]
