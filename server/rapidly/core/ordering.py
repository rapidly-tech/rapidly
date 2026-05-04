"""Query-string sorting parser and OpenAPI-aware dependency builder.

The ``Sorting`` type alias represents a single ordering criterion — a
``(property_enum, is_descending)`` pair.  ``SortingGetter`` is a callable
FastAPI dependency that parses the ``?sorting=`` query parameter and
returns a list of ``Sorting`` tuples, validating each value against a
caller-supplied ``StrEnum``.

Descending order is indicated by prefixing the criterion name with ``-``.
"""

from enum import StrEnum
from inspect import Parameter, Signature
from typing import Any

from fastapi import Query
from makefun import with_signature

from rapidly.errors import RequestValidationError

type Sorting[PE] = tuple[PE, bool]

_DESC_PREFIX: str = "-"

_SORTING_DESCRIPTION: str = (
    "Sorting criterion. "
    "Several criteria can be used simultaneously and will be applied in order. "
    "Add a minus sign `-` before the criteria name to sort by descending order."
)


# ── Internal parser ────────────────────────────────────────────────────


class _SortingGetter[PE: StrEnum]:
    """Parses ``?sorting=`` query values into validated ``Sorting`` tuples."""

    __slots__ = ("_default_sorting", "_enum_cls")

    def __init__(
        self, sort_property_enum: type[PE], default_sorting: list[str]
    ) -> None:
        self._enum_cls = sort_property_enum
        self._default_sorting = default_sorting

    async def __call__(self, sorting: list[str] | None) -> list[Sorting[PE]]:
        raw = sorting if sorting is not None else self._default_sorting

        parsed: list[tuple[PE, bool]] = []
        for criterion in raw:
            descending = criterion.startswith(_DESC_PREFIX)
            name = criterion.removeprefix(_DESC_PREFIX)
            try:
                parsed.append((self._enum_cls(name), descending))
            except ValueError:
                raise RequestValidationError(
                    [
                        {
                            "loc": ("query", "sorting"),
                            "input": name,
                            "msg": "Invalid sorting criterion.",
                            "type": "enum",
                        }
                    ]
                )
        return parsed


# ── OpenAPI enum builder ───────────────────────────────────────────────


def _build_sort_enum(base: type[StrEnum]) -> type[StrEnum]:
    """Create an enum with both ascending and descending variants for each value."""
    values: list[str] = []
    for member in base:
        values.append(member.value)
        values.append(f"{_DESC_PREFIX}{member.value}")
    return StrEnum(base.__name__, values)  # type: ignore[return-value]


# ── Public factory ─────────────────────────────────────────────────────


def SortingGetter[PE: StrEnum](
    sort_property_enum: type[PE], default_sorting: list[str]
) -> _SortingGetter[PE]:
    """Build a ``_SortingGetter`` whose ``__call__`` signature advertises the
    allowed sorting values to FastAPI's OpenAPI generator.
    """
    sort_property_full_enum = _build_sort_enum(sort_property_enum)

    parameters: list[Parameter] = [
        Parameter(name="self", kind=Parameter.POSITIONAL_OR_KEYWORD),
        Parameter(
            name="sorting",
            kind=Parameter.POSITIONAL_OR_KEYWORD,
            default=Query(
                default_sorting,
                description=_SORTING_DESCRIPTION,
            ),
            annotation=list[sort_property_full_enum] | None,  # type: ignore[valid-type]
        ),
    ]
    signature = Signature(parameters)

    class _SortingGetterSignature(_SortingGetter[Any]):
        @with_signature(signature)
        async def __call__(self, sorting: Any) -> list[Sorting[Any]]:
            return await super().__call__(sorting)

    return _SortingGetterSignature(sort_property_enum, default_sorting)
