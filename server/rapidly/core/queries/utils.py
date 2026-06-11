"""Shared query utilities."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.sql.elements import ColumnElement
    from sqlalchemy.sql.operators import ColumnOperators


def escape_like(value: str) -> str:
    """Escape SQL LIKE metacharacters (``%``, ``_``, ``\\``) in *value*.

    Prevents user-supplied search terms from being interpreted as
    wildcard patterns when used inside ``ILIKE``/``LIKE`` expressions.

    **Important:** ``escape_like`` alone is not enough. Postgres
    ``LIKE`` ignores backslash escapes unless an ``ESCAPE`` clause is
    declared on the ``ilike()`` call.  Use :func:`ilike_substring`
    below — it pairs the two correctly in one helper, removing the
    foot-gun.
    """
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def ilike_substring(
    column: "ColumnOperators", value: str, *, anchor: str = "both"
) -> "ColumnElement[bool]":
    """Return ``column ILIKE %value%`` with wildcards in *value* escaped.

    Wraps :func:`escape_like` and passes the matching ``escape="\\"``
    clause to SQLAlchemy's ``ilike()`` so the escapes are honoured by
    Postgres.  Without the explicit clause, ``LIKE`` treats backslash
    as a literal character and user-supplied ``%`` / ``_`` keep their
    wildcard meaning — see [[feedback-escape-like-needs-escape-clause]].

    :param column: any SQLAlchemy column / expression with an
        ``ilike(...)`` operator (most commonly ``Model.field`` or
        ``func.lower(Model.field)``).
    :param value: raw user input; whitespace is preserved (callers
        should strip before calling if they want "no filter on blank").
    :param anchor: where to put the ``%`` wildcards:

        - ``"both"`` (default) — ``%value%`` (substring).
        - ``"prefix"`` — ``value%`` (value is the prefix).
        - ``"suffix"`` — ``%value`` (value is the suffix).
    """
    from typing import cast

    from sqlalchemy.sql.elements import ColumnElement

    escaped = escape_like(value)
    if anchor == "both":
        pattern = f"%{escaped}%"
    elif anchor == "prefix":
        pattern = f"{escaped}%"
    elif anchor == "suffix":
        pattern = f"%{escaped}"
    else:
        raise ValueError(
            f"ilike_substring: unknown anchor {anchor!r}; "
            "expected 'both', 'prefix', or 'suffix'."
        )
    # ``ilike`` returns a boolean ColumnElement at runtime; the type
    # stub generalises to ``ColumnOperators``, so cast to keep callers
    # type-safe when composing with ``or_`` / ``and_``.
    return cast(ColumnElement[bool], column.ilike(pattern, escape="\\"))
