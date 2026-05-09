"""DaisyUI collapse-based accordion for the admin panel.

Items that share the same *accordion_name* form a radio group so that
expanding one panel automatically collapses the others.
"""

import contextlib
from collections.abc import Generator

from tagflow import tag, text


@contextlib.contextmanager
def item(accordion_name: str, title: str) -> Generator[None]:
    """Emit a single collapsible panel.

    Args:
        accordion_name: Shared ``name`` attribute that groups panels
            into a mutually exclusive set.
        title: Heading displayed on the clickable summary bar.
    """
    with tag.div(classes="collapse collapse-arrow bg-base-100 border border-base-300"):
        with tag.input(type="radio", name=accordion_name):
            pass
        with tag.div(classes="collapse-title font-semibold"):
            text(title)
        with tag.div(classes="collapse-content"):
            yield


__all__ = ["item"]
