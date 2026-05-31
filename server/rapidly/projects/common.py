"""Shared Pydantic field types for the projects domain."""

from typing import Annotated

from pydantic import Field

# 6- or 8-digit hex colour (``#rrggbb`` or ``#rrggbbaa``).  Stored verbatim
# and rendered as a CSS value in the UI, so the strict pattern keeps the
# field safe from arbitrary string injection.
HexColor = Annotated[
    str,
    Field(
        pattern=r"^#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$",
        description="CSS hex colour (#rrggbb or #rrggbbaa).",
    ),
]

OptionalHexColor = Annotated[
    str | None,
    Field(
        default=None,
        pattern=r"^#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$",
        description="Optional CSS hex colour.",
    ),
]
