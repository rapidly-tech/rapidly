"""One-click copy-to-clipboard button using Hyperscript.

Relies on the ``CopyToClipboard`` Hyperscript behaviour defined in the
base page template (see ``_base.py``).  After a successful copy the
clipboard icon is replaced with a checkmark for five seconds.
"""

import contextlib
from collections.abc import Generator

from tagflow import tag


@contextlib.contextmanager
def clipboard_button(text: str) -> Generator[None]:
    """Render a small icon button that copies *text* to the clipboard.

    Args:
        text: The string to write to the system clipboard on click.
    """
    with tag.button(
        type="button",
        classes="font-normal cursor-pointer",
        _=f"install CopyToClipboard(text: '{text}')",
    ):
        with tag.div(classes="icon-clipboard"):
            pass
        with tag.div(classes="icon-clipboard-check hidden"):
            pass
    yield


__all__ = ["clipboard_button"]
