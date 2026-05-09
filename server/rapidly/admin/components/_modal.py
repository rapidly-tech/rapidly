"""Generic modal dialog shell for the admin panel.

Wraps content in a DaisyUI ``<dialog>`` with a close button, title,
and backdrop click-to-dismiss.  Callers yield into the modal body.
"""

import contextlib
from collections.abc import Generator

from tagflow import attr, tag, text


@contextlib.contextmanager
def modal(title: str, *, open: bool = False) -> Generator[None]:
    """Render a centred modal dialog.

    Args:
        title: Heading displayed at the top of the modal box.
        open: When ``True`` the dialog starts in the open state.
    """
    with tag.dialog(classes="modal modal-bottom sm:modal-middle"):
        if open:
            attr("open", True)

        with tag.div(classes="modal-box"):
            # Dismiss button
            with tag.form(method="dialog"):
                with tag.button(
                    classes="btn btn-sm btn-circle btn-ghost absolute right-2 top-2"
                ):
                    with tag.div(classes="icon-close"):
                        pass

            with tag.h3(classes="text-lg font-bold mb-4"):
                text(title)

            # Caller fills the body here.
            yield

        # Click-outside-to-close backdrop.
        with tag.form(method="dialog", classes="modal-backdrop"):
            with tag.button():
                pass


__all__ = ["modal"]
