"""Confirmation modal for deleting a user's identity verification.

Warns the admin that this will reset the verification status and
redact personal data from Stripe.
"""

import contextlib
from collections.abc import Generator

from tagflow import attr

from rapidly.admin.components import confirmation_dialog
from rapidly.models import User

_CONFIRM_MESSAGE = (
    "Are you sure you want to delete this user's identity verification? "
    "This will reset their verification status to unverified and redact "
    "all personal data from Stripe. This action cannot be undone."
)


class DeleteIdentityVerificationModal:
    def __init__(self, user: User, form_action: str):
        self._user = user
        self._action = form_action

    @contextlib.contextmanager
    def render(self) -> Generator[None]:
        with confirmation_dialog(
            "Delete Identity Verification",
            _CONFIRM_MESSAGE,
            variant="error",
            confirm_text="Delete Verification",
            open=True,
        ):
            attr("hx-post", self._action)
            attr("hx-target", "#modal")
            attr("hx-vals", '{"confirm": "true"}')

        yield


__all__ = ["DeleteIdentityVerificationModal"]
