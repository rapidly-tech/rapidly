"""Polymorphic custom-field hierarchy for workspace-defined data fields.

Custom fields let workspace admins extend the share data model with
arbitrary typed attributes.  Each field type (text, number, date,
checkbox, select) is a concrete subclass that knows how to produce a
Pydantic ``Field`` definition at runtime.

The JSONB ``properties`` column carries per-type configuration (e.g.
min/max constraints for numbers, option lists for selects).
"""

from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Annotated, Any, Literal, NotRequired, TypedDict
from uuid import UUID

from annotated_types import Ge, Le, Len, MinLen
from pydantic import AfterValidator, Field, ValidationInfo
from sqlalchemy import ForeignKey, String, UniqueConstraint, Uuid
from sqlalchemy.dialects.postgresql import CITEXT, JSONB
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from rapidly.core.db.models import BaseEntity
from rapidly.core.metadata import MetadataMixin

if TYPE_CHECKING:
    from rapidly.models import Workspace

# Signed 32-bit integer boundaries used for numeric range validation.
INT32_MIN = -(2**31)
INT32_MAX = 2**31 - 1

# -- Reusable annotated type aliases -----------------------------------------

PositiveBoundedInt = Annotated[int, Ge(0), Le(INT32_MAX)]
BoundedInt = Annotated[int, Ge(INT32_MIN), Le(INT32_MAX)]
NonEmptyString = Annotated[str, Len(min_length=1)]


# -- Field type enumeration -------------------------------------------------


class CustomFieldType(StrEnum):
    """Discriminator values for the custom-field type hierarchy."""

    text = "text"
    number = "number"
    date = "date"
    checkbox = "checkbox"
    select = "select"

    def get_model(self) -> type["CustomField"]:
        """Return the concrete model class for this field type."""
        _registry: dict[CustomFieldType, type[CustomField]] = {
            CustomFieldType.text: CustomFieldText,
            CustomFieldType.number: CustomFieldNumber,
            CustomFieldType.date: CustomFieldDate,
            CustomFieldType.checkbox: CustomFieldCheckbox,
            CustomFieldType.select: CustomFieldSelect,
        }
        return _registry[self]


# -- Pydantic cross-field validator ------------------------------------------


def validate_ge_le(v: int, info: ValidationInfo) -> int:
    """Ensure ``le`` >= ``ge`` when both bounds are present."""
    ge = info.data.get("ge")
    if ge is not None and v is not None and ge > v:
        raise ValueError(
            "Greater than or equal (ge) must be less than or equal to "
            "Less than or equal (le)"
        )
    return v


# -- Properties TypedDicts (JSONB shapes per field type) ---------------------


class CustomFieldProperties(TypedDict):
    """Base form-rendering hints shared by every field type."""

    form_label: NotRequired[NonEmptyString]
    form_help_text: NotRequired[NonEmptyString]
    form_placeholder: NotRequired[NonEmptyString]


class CustomFieldTextProperties(CustomFieldProperties):
    textarea: NotRequired[bool]
    min_length: NotRequired[PositiveBoundedInt]
    max_length: NotRequired[PositiveBoundedInt]


class ComparableProperties(TypedDict):
    """Shared range-constraint shape for number and date fields."""

    ge: NotRequired[BoundedInt]
    le: NotRequired[Annotated[BoundedInt, AfterValidator(validate_ge_le)]]


class CustomFieldNumberProperties(CustomFieldProperties, ComparableProperties):
    pass


class CustomFieldDateProperties(CustomFieldProperties, ComparableProperties):
    pass


class CustomFieldCheckboxProperties(CustomFieldProperties):
    pass


class CustomFieldSelectOption(TypedDict):
    value: NonEmptyString
    label: NonEmptyString


class CustomFieldSelectProperties(CustomFieldProperties):
    options: Annotated[list[CustomFieldSelectOption], MinLen(1)]


# -- Base custom field model -------------------------------------------------


class CustomField(MetadataMixin, BaseEntity):
    """Polymorphic root for workspace-defined custom data fields.

    The slug + workspace_id pair is unique so that field references in
    API payloads are both human-readable and unambiguous.
    """

    __tablename__ = "custom_fields"
    __table_args__ = (UniqueConstraint("slug", "workspace_id"),)

    # -- Workspace association -----------------------------------------------

    workspace_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("workspaces.id", ondelete="cascade"),
        nullable=False,
        index=True,
    )

    @declared_attr
    def workspace(cls) -> Mapped["Workspace"]:
        return relationship("Workspace", lazy="raise")

    # -- Field identity ------------------------------------------------------

    slug: Mapped[str] = mapped_column(
        CITEXT,
        nullable=False,
        # No standalone index -- the unique constraint covers slug lookups
        index=False,
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    type: Mapped[CustomFieldType] = mapped_column(String, nullable=False, index=True)

    # -- Per-type configuration ----------------------------------------------

    properties: Mapped[CustomFieldProperties] = mapped_column(
        JSONB, nullable=False, default=dict
    )

    # -- Subclass contract ---------------------------------------------------

    def get_field_definition(self, required: bool) -> tuple[Any, Any]:
        """Return (annotation, Field) for dynamic Pydantic model construction."""
        raise NotImplementedError()

    __mapper_args__ = {
        "polymorphic_on": "type",
    }


# -- Concrete field-type subclasses ------------------------------------------


class CustomFieldText(CustomField):
    """Free-form text input, optionally rendered as a textarea."""

    type: Mapped[Literal[CustomFieldType.text]] = mapped_column(
        use_existing_column=True
    )
    properties: Mapped[CustomFieldTextProperties] = mapped_column(
        use_existing_column=True
    )

    __mapper_args__ = {
        "polymorphic_identity": CustomFieldType.text,
        "polymorphic_load": "inline",
    }

    def get_field_definition(self, required: bool) -> tuple[Any, Any]:
        annotation = str if required else str | None
        field = Field(
            default=None if not required else ...,
            min_length=self.properties.get("min_length"),
            max_length=self.properties.get("max_length"),
        )
        return (annotation, field)


class CustomFieldNumber(CustomField):
    """Integer field with optional min/max bounds."""

    type: Mapped[Literal[CustomFieldType.number]] = mapped_column(
        use_existing_column=True
    )
    properties: Mapped[CustomFieldNumberProperties] = mapped_column(
        use_existing_column=True
    )

    __mapper_args__ = {
        "polymorphic_identity": CustomFieldType.number,
        "polymorphic_load": "inline",
    }

    def get_field_definition(self, required: bool) -> tuple[Any, Any]:
        lower = self.properties.get("ge")
        upper = self.properties.get("le")
        annotation = int if required else int | None
        field = Field(
            default=None if not required else ...,
            ge=lower if lower is not None else INT32_MIN,
            le=upper if upper is not None else INT32_MAX,
        )
        return (annotation, field)


class CustomFieldDate(CustomField):
    """Date picker with optional epoch-based bounds."""

    type: Mapped[Literal[CustomFieldType.date]] = mapped_column(
        use_existing_column=True
    )
    properties: Mapped[CustomFieldDateProperties] = mapped_column(
        use_existing_column=True
    )

    __mapper_args__ = {
        "polymorphic_identity": CustomFieldType.date,
        "polymorphic_load": "inline",
    }

    def get_field_definition(self, required: bool) -> tuple[Any, Any]:
        raw_ge = self.properties.get("ge")
        raw_le = self.properties.get("le")
        lower_date = datetime.fromtimestamp(raw_ge, tz=UTC).date() if raw_ge else None
        upper_date = datetime.fromtimestamp(raw_le, tz=UTC).date() if raw_le else None
        annotation = datetime if required else datetime | None
        field = Field(
            default=None if not required else ..., ge=lower_date, le=upper_date
        )
        return (annotation, field)


class CustomFieldCheckbox(CustomField):
    """Boolean toggle, required means must be True."""

    type: Mapped[Literal[CustomFieldType.checkbox]] = mapped_column(
        use_existing_column=True
    )
    properties: Mapped[CustomFieldCheckboxProperties] = mapped_column(
        use_existing_column=True
    )

    __mapper_args__ = {
        "polymorphic_identity": CustomFieldType.checkbox,
        "polymorphic_load": "inline",
    }

    def get_field_definition(self, required: bool) -> tuple[Any, Any]:
        annotation = Literal[True] if required else bool
        field = Field(default=False if not required else ...)
        return (annotation, field)


class CustomFieldSelect(CustomField):
    """Single-value dropdown built from a configured option list."""

    type: Mapped[Literal[CustomFieldType.select]] = mapped_column(
        use_existing_column=True
    )
    properties: Mapped[CustomFieldSelectProperties] = mapped_column(
        use_existing_column=True
    )

    __mapper_args__ = {
        "polymorphic_identity": CustomFieldType.select,
        "polymorphic_load": "inline",
    }

    def get_field_definition(self, required: bool) -> tuple[Any, Any]:
        allowed_values = tuple(option["value"] for option in self.properties["options"])
        literal_type = Literal[allowed_values]  # type: ignore
        annotation = literal_type if required else literal_type | None  # pyright: ignore
        field = Field(default=None if not required else ...)
        return (annotation, field)
