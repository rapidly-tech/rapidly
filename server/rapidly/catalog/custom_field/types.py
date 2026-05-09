"""Custom-field definition and share-attachment Pydantic models.

Supports a discriminated union of field types (text, number, date,
checkbox, select) with create / update payloads, plus the
``AttachedCustomField`` schema for ordering and requirement flags
when fields are linked to products.
"""

from typing import Annotated, Literal

from pydantic import UUID4, Discriminator, Field, StringConstraints, TypeAdapter

from rapidly.core.metadata import (
    MetadataInputMixin,
    MetadataOutputMixin,
)
from rapidly.core.types import (
    AuditableSchema,
    ClassName,
    IdentifiableSchema,
    MergeJSONSchema,
    Schema,
    SetSchemaReference,
)
from rapidly.models.custom_field import (
    CustomFieldCheckboxProperties,
    CustomFieldDateProperties,
    CustomFieldNumberProperties,
    CustomFieldSelectProperties,
    CustomFieldTextProperties,
    CustomFieldType,
)
from rapidly.platform.workspace.types import WorkspaceID

# ---------------------------------------------------------------------------
# Shared field constraints
# ---------------------------------------------------------------------------

Slug = Annotated[
    str,
    StringConstraints(to_lower=True, min_length=1, pattern=r"^[a-z0-9-_]+$"),
    Field(
        description=(
            "Identifier of the custom field. "
            "It'll be used as key when storing the value. "
            "Must be unique across the workspace."
            "It can only contain ASCII letters, numbers and hyphens."
        ),
        min_length=1,
    ),
]
Name = Annotated[str, Field(description="Name of the custom field.", min_length=1)]


# ---------------------------------------------------------------------------
# Attachment schemas (field <-> share link)
# ---------------------------------------------------------------------------


class AttachedCustomFieldCreate(Schema):
    """Payload to attach a custom field to a resource."""

    custom_field_id: UUID4 = Field(description="ID of the custom field to attach.")
    required: bool = Field(
        description="Whether the value is required for this custom field."
    )


AttachedCustomFieldListCreate = Annotated[
    list[AttachedCustomFieldCreate],
    Field(description="List of custom fields to attach."),
]


class AttachedCustomField(Schema):
    """A custom field attached to a resource with ordering and requirement flags."""

    custom_field_id: UUID4 = Field(description="ID of the custom field.")
    custom_field: "CustomField"
    order: int = Field(description="Order of the custom field in the resource.")
    required: bool = Field(
        description="Whether the value is required for this custom field."
    )


# ---------------------------------------------------------------------------
# Per-type read schemas
# ---------------------------------------------------------------------------


class CustomFieldBase(MetadataOutputMixin, IdentifiableSchema, AuditableSchema):
    """Base read model for all custom field types."""

    type: CustomFieldType = Field(description="Data type of the custom field.")
    slug: str = Field(
        description="Identifier of the custom field. "
        "It'll be used as key when storing the value."
    )
    name: str = Field(description="Name of the custom field.")
    workspace_id: WorkspaceID = Field(
        description="The ID of the workspace owning the custom field."
    )


class CustomFieldText(CustomFieldBase):
    """Custom field of type text."""

    type: Literal[CustomFieldType.text]
    properties: CustomFieldTextProperties


class CustomFieldNumber(CustomFieldBase):
    """Custom field of type number."""

    type: Literal[CustomFieldType.number]
    properties: CustomFieldNumberProperties


class CustomFieldDate(CustomFieldBase):
    """Custom field of type date."""

    type: Literal[CustomFieldType.date]
    properties: CustomFieldDateProperties


class CustomFieldCheckbox(CustomFieldBase):
    """Custom field of type checkbox."""

    type: Literal[CustomFieldType.checkbox]
    properties: CustomFieldCheckboxProperties


class CustomFieldSelect(CustomFieldBase):
    """Custom field of type select."""

    type: Literal[CustomFieldType.select]
    properties: CustomFieldSelectProperties


CustomField = Annotated[
    CustomFieldText
    | CustomFieldNumber
    | CustomFieldDate
    | CustomFieldCheckbox
    | CustomFieldSelect,
    Discriminator("type"),
    SetSchemaReference("CustomField"),
    MergeJSONSchema({"title": "CustomField"}),
    ClassName("CustomField"),
]

CustomFieldAdapter: TypeAdapter[CustomField] = TypeAdapter(CustomField)


# ---------------------------------------------------------------------------
# Create schemas
# ---------------------------------------------------------------------------


class CustomFieldCreateBase(MetadataInputMixin, Schema):
    """Base payload for creating a custom field."""

    type: CustomFieldType = Field(description="Data type of the custom field.")
    slug: Slug
    name: Name
    workspace_id: WorkspaceID | None = Field(
        default=None,
        description=(
            "The ID of the workspace owning the custom field. "
            "**Required unless you use an workspace token.**"
        ),
    )


class CustomFieldCreateText(CustomFieldCreateBase):
    """Create a text custom field."""

    type: Literal[CustomFieldType.text]
    properties: CustomFieldTextProperties


class CustomFieldCreateNumber(CustomFieldCreateBase):
    """Create a number custom field."""

    type: Literal[CustomFieldType.number]
    properties: CustomFieldNumberProperties


class CustomFieldCreateDate(CustomFieldCreateBase):
    """Create a date custom field."""

    type: Literal[CustomFieldType.date]
    properties: CustomFieldDateProperties


class CustomFieldCreateCheckbox(CustomFieldCreateBase):
    """Create a checkbox custom field."""

    type: Literal[CustomFieldType.checkbox]
    properties: CustomFieldCheckboxProperties


class CustomFieldCreateSelect(CustomFieldCreateBase):
    """Create a select custom field."""

    type: Literal[CustomFieldType.select]
    properties: CustomFieldSelectProperties


CustomFieldCreate = Annotated[
    CustomFieldCreateText
    | CustomFieldCreateNumber
    | CustomFieldCreateDate
    | CustomFieldCreateCheckbox
    | CustomFieldCreateSelect,
    Discriminator("type"),
    SetSchemaReference("CustomFieldCreate"),
]


# ---------------------------------------------------------------------------
# Update schemas
# ---------------------------------------------------------------------------


class CustomFieldUpdateBase(MetadataInputMixin, Schema):
    """Base payload for updating a custom field."""

    name: Name | None = None
    slug: Slug | None = None


class CustomFieldUpdateText(CustomFieldUpdateBase):
    """Update a text custom field."""

    type: Literal[CustomFieldType.text]
    properties: CustomFieldTextProperties | None = None


class CustomFieldUpdateNumber(CustomFieldUpdateBase):
    """Update a number custom field."""

    type: Literal[CustomFieldType.number]
    properties: CustomFieldNumberProperties | None = None


class CustomFieldUpdateDate(CustomFieldUpdateBase):
    """Update a date custom field."""

    type: Literal[CustomFieldType.date]
    properties: CustomFieldDateProperties | None = None


class CustomFieldUpdateCheckbox(CustomFieldUpdateBase):
    """Update a checkbox custom field."""

    type: Literal[CustomFieldType.checkbox]
    properties: CustomFieldCheckboxProperties | None = None


class CustomFieldUpdateSelect(CustomFieldUpdateBase):
    """Update a select custom field."""

    type: Literal[CustomFieldType.select]
    properties: CustomFieldSelectProperties | None = None


CustomFieldUpdate = Annotated[
    CustomFieldUpdateText
    | CustomFieldUpdateNumber
    | CustomFieldUpdateDate
    | CustomFieldUpdateCheckbox
    | CustomFieldUpdateSelect,
    Discriminator("type"),
    SetSchemaReference("CustomFieldUpdate"),
]
