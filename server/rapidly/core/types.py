"""Pydantic base schemas, validators, and OpenAPI annotation helpers for Rapidly."""

import dataclasses
import json
from collections.abc import Sequence
from datetime import datetime
from typing import Annotated, Any, Literal, cast, get_args, overload

from pydantic import (
    UUID4,
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    GetCoreSchemaHandler,
    GetJsonSchemaHandler,
    HttpUrl,
    PlainSerializer,
)
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import CoreSchema, core_schema
from slugify import slugify

# ── Base schemas ──────────────────────────────────────────────────────


class Schema(BaseModel):
    """Root Pydantic schema with ORM-mode enabled by default."""

    model_config = ConfigDict(from_attributes=True)


class IdentifiableSchema(Schema):
    """Schema that carries a UUID primary key."""

    id: UUID4 = Field(..., description="The ID of the object.")
    model_config = ConfigDict(json_schema_mode_override="serialization")


class AuditableSchema(Schema):
    """Schema with created/modified audit timestamps."""

    created_at: datetime = Field(description="Creation timestamp of the object.")
    modified_at: datetime | None = Field(
        description="Last modification timestamp of the object."
    )


# ── String validators ─────────────────────────────────────────────────


def empty_str_to_none(value: str | None) -> str | None:
    """Strip whitespace; return ``None`` for empty strings."""
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return value


EmptyStrToNoneValidator = AfterValidator(empty_str_to_none)
EmptyStrToNone = Annotated[str | None, EmptyStrToNoneValidator]

_SLUG_CHARSET_MSG = "The slug can only contain ASCII letters, numbers and hyphens."


def _validate_slug(value: str) -> str:
    if slugify(value) != value:
        raise ValueError(_SLUG_CHARSET_MSG)
    return value


SlugValidator = AfterValidator(_validate_slug)

# ── Serialisation helpers ─────────────────────────────────────────────

_uuid_to_str = PlainSerializer(lambda v: str(v), return_type=str)

UUID4ToStr = Annotated[UUID4, _uuid_to_str]
HttpUrlToStr = Annotated[HttpUrl, _uuid_to_str]


# ── OpenAPI metadata annotations ─────────────────────────────────────


@dataclasses.dataclass(slots=True)
class ClassName:
    """Annotation metadata that overrides the Pydantic-generated schema name.

    Consumed by ``PaginatedList`` to produce shorter OpenAPI names for union types.
    """

    name: str

    def __hash__(self) -> int:
        return hash(self.name)


@dataclasses.dataclass(slots=True)
class MergeJSONSchema:
    json_schema: JsonSchemaValue
    mode: Literal["validation", "serialization"] | None = None

    def __get_pydantic_json_schema__(
        self, core_schema: core_schema.CoreSchema, handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        mode = self.mode or handler.mode
        json_schema = handler(core_schema)
        if mode != handler.mode:
            return json_schema
        return {**json_schema, **self.json_schema}

    def __hash__(self) -> int:
        return hash(type(self.mode))


@dataclasses.dataclass(slots=True)
class SetSchemaReference:
    ref_name: str

    def __get_pydantic_core_schema__(
        self, source_type: Any, handler: GetCoreSchemaHandler
    ) -> CoreSchema:
        schema = handler(source_type)
        schema["ref"] = self.ref_name  # type: ignore
        return schema

    def __hash__(self) -> int:
        return hash(type(self.ref_name))


@dataclasses.dataclass(slots=True)
class SelectorWidget:
    resource_root: str
    resource_name: str
    display_property: str

    def __get_pydantic_json_schema__(
        self, core_schema: core_schema.CoreSchema, handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        json_schema = handler(core_schema)
        return {**json_schema, **self._get_extra_attributes()}

    def _get_extra_attributes(self) -> dict[str, Any]:
        return {
            "x-rapidly-selector-widget": {
                "resourceRoot": self.resource_root,
                "resourceName": self.resource_name,
                "displayProperty": self.display_property,
            }
        }

    def __hash__(self) -> int:
        return hash(json.dumps(self._get_extra_attributes()))


# ── Query parameter helpers ───────────────────────────────────────────


class MultipleQueryFilter[Q](Sequence[Q]):
    """Query parameter that normalises a single value or list to ``Sequence[Q]``."""

    __slots__ = ("v",)

    def __init__(self, v: Sequence[Q]):
        self.v = v

    @overload
    def __getitem__(self, s: int) -> Q: ...

    @overload
    def __getitem__(self, s: slice) -> Sequence[Q]: ...

    def __getitem__(self, s: int | slice) -> Q | Sequence[Q]:
        return self.v[s]

    def __len__(self) -> int:
        return len(self.v)

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source: Any, handler: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        args = get_args(source)
        if len(args) == 0:
            raise TypeError("QueryFilter requires at least one type argument")

        generic_type = args[0]
        sequence_schema = handler.generate_schema(Sequence[generic_type])  # type: ignore
        scalar_schema = handler.generate_schema(generic_type)
        union_schema = core_schema.union_schema([scalar_schema, sequence_schema])

        return core_schema.no_info_after_validator_function(
            cls._scalar_to_sequence, handler(union_schema)
        )

    @classmethod
    def _scalar_to_sequence(cls, v: Q | Sequence[Q]) -> Sequence[Q]:
        if isinstance(v, Sequence) and not isinstance(v, str):
            return v
        return [cast(Q, v)]  # type: ignore[redundant-cast]


# ── OpenAPI example UUIDs ─────────────────────────────────────────────

WORKSPACE_ID_EXAMPLE: str = "1dbfc517-0bbf-4301-9ba8-555ca42b9737"
CUSTOMER_ID_EXAMPLE: str = "992fae2a-2a17-4b7a-8d9e-e287cf90131b"
