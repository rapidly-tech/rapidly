"""Status badges with semantic DaisyUI colouring.

Maps lifecycle states to appropriate badge classes and ARIA labels,
then renders compact inline ``<span>`` or ``<div>`` elements.
"""

import contextlib
from collections.abc import Generator
from typing import Any

from tagflow import classes, tag, text

from rapidly.models.user import IdentityVerificationStatus
from rapidly.models.workspace import WorkspaceStatus

# Per-status visual config: CSS class string and accessible label.
_STATUS_STYLES: dict[WorkspaceStatus, tuple[str, str]] = {
    WorkspaceStatus.ACTIVE: (
        "badge-ghost border border-base-300",
        "active status",
    ),
    WorkspaceStatus.INITIAL_REVIEW: (
        "badge-warning",
        "initial review status",
    ),
    WorkspaceStatus.ONGOING_REVIEW: (
        "badge-warning",
        "ongoing review status",
    ),
    WorkspaceStatus.DENIED: (
        "badge-ghost border border-base-300",
        "denied status",
    ),
    WorkspaceStatus.CREATED: (
        "badge-ghost border border-base-300",
        "created status",
    ),
    WorkspaceStatus.ONBOARDING_STARTED: (
        "badge-ghost border border-base-300",
        "onboarding started status",
    ),
}

_FALLBACK_STYLE = ("badge-ghost border border-base-300", "unknown status")


@contextlib.contextmanager
def status_badge(
    status: WorkspaceStatus,
    *,
    show_icon: bool = False,
    **kwargs: Any,
) -> Generator[None]:
    """Render a coloured badge for *status*.

    Args:
        status: Current workspace lifecycle state.
        show_icon: Reserved for future icon support.
        **kwargs: Additional HTML attributes on the ``<span>``.
    """
    css_class, aria = _STATUS_STYLES.get(status, _FALLBACK_STYLE)

    with tag.span(classes="badge", **kwargs):
        classes(css_class)
        if "aria-label" not in kwargs:
            kwargs["aria-label"] = aria

        text(status.get_display_name())
        yield


@contextlib.contextmanager
def identity_verification_status_badge(
    status: IdentityVerificationStatus,
) -> Generator[None]:
    """Render a coloured badge for *status*."""
    with tag.div(classes="badge"):
        if status == IdentityVerificationStatus.verified:
            classes("badge-success")
        elif status in {
            IdentityVerificationStatus.pending,
            IdentityVerificationStatus.failed,
        }:
            classes("badge-warning")
        else:
            classes("badge-neutral")
        text(status.get_display_name())
    yield


__all__ = ["identity_verification_status_badge", "status_badge"]
