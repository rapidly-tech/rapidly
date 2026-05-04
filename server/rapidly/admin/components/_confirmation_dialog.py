"""Confirmation dialog for destructive admin actions.

Wraps a DaisyUI modal with a semantic icon, message text, and
cancel / confirm buttons.  The caller yields into the confirm button
to attach HTMX attributes or form actions.
"""

import contextlib
from collections.abc import Generator
from typing import Any, Literal, TypedDict

from tagflow import attr, tag, text

from ._button import Variant as ButtonVariant
from ._button import button

Variant = Literal["info", "success", "warning", "error"]


class _VariantSpec(TypedDict):
    icon: str
    button: ButtonVariant


_VARIANT_SPECS: dict[str, _VariantSpec] = {
    "info": {"icon": "\u2139\ufe0f", "button": "info"},
    "success": {"icon": "\u2705", "button": "success"},
    "warning": {"icon": "\u26a0\ufe0f", "button": "warning"},
    "error": {"icon": "\u274c", "button": "error"},
}


@contextlib.contextmanager
def confirmation_dialog(
    title: str,
    message: str,
    *,
    variant: Variant = "warning",
    confirm_text: str = "Confirm",
    cancel_text: str = "Cancel",
    open: bool = False,
    **kwargs: Any,
) -> Generator[None]:
    """Render a confirmation modal with icon, message, and action buttons.

    The context-manager body is placed inside the confirm button, so the
    caller can attach ``hx_post``, ``hx_delete``, or a ``<form>`` action.

    Args:
        title: Heading shown next to the variant icon.
        message: Explanatory text displayed below the heading.
        variant: Controls the icon and confirm-button colour.
        confirm_text: Label for the primary action button.
        cancel_text: Label for the dismiss button.
        open: Start the dialog in the visible state.
        **kwargs: Forwarded to the ``<dialog>`` element.
    """
    spec = _VARIANT_SPECS.get(variant, _VARIANT_SPECS["warning"])

    with tag.dialog(classes="modal modal-bottom sm:modal-middle", **kwargs):
        if open:
            attr("open", True)

        with tag.div(classes="modal-box"):
            # Close (X) button
            with tag.form(method="dialog"):
                with tag.button(
                    classes="btn btn-sm btn-circle btn-ghost absolute right-2 top-2"
                ):
                    with tag.div(classes="icon-close"):
                        pass

            # Header row: icon + title
            with tag.div(classes="flex items-center gap-3 mb-4"):
                with tag.div(classes="text-4xl"):
                    text(spec["icon"])
                with tag.h3(classes="text-lg font-bold"):
                    text(title)

            # Body text
            with tag.p(classes="text-base-content/80 mb-6"):
                text(message)

            # Action row
            with tag.div(classes="modal-action"):
                with tag.form(method="dialog"):
                    with button(variant="secondary", size="md"):
                        text(cancel_text)
                with button(variant=spec["button"], size="md"):
                    text(confirm_text)
                    yield

        # Backdrop click-to-close
        with tag.form(method="dialog", classes="modal-backdrop"):
            with tag.button():
                pass


__all__ = ["Variant", "confirmation_dialog"]
