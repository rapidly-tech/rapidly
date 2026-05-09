"""Shared query utilities."""


def escape_like(value: str) -> str:
    """Escape SQL LIKE metacharacters (``%``, ``_``, ``\\``) in *value*.

    Prevents user-supplied search terms from being interpreted as
    wildcard patterns when used inside ``ILIKE``/``LIKE`` expressions.
    """
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
