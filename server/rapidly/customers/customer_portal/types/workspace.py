"""Pydantic schemas for the customer-portal workspace view.

Provides a read-only ``Workspace`` schema tailored for the portal,
exposing only public-facing fields like name, slug, avatar, and
storefront settings.
"""

from typing import Self

from pydantic import Field, model_validator

from rapidly.catalog.file.types import ShareMediaFileRead
from rapidly.catalog.share.types import ShareBase, SharePrice
from rapidly.core.types import Schema
from rapidly.models.workspace import WorkspaceCustomerPortalSettings
from rapidly.platform.workspace.types import (
    WorkspacePublicBase,
)


class CustomerProduct(ShareBase):
    """Schema of a share for customer portal."""

    prices: list[SharePrice] = Field(
        description="List of available prices for this share."
    )
    medias: list[ShareMediaFileRead] = Field(
        description="The medias associated to the share."
    )


class CustomerWorkspaceFeatureSettings(Schema):
    """Feature flags exposed to the customer portal."""

    member_model_enabled: bool = Field(
        default=False,
        description="Whether the member model is enabled for this workspace.",
    )


class CustomerWorkspace(WorkspacePublicBase):
    customer_portal_settings: WorkspaceCustomerPortalSettings = Field(
        description="Settings related to the customer portal",
    )
    workspace_features: CustomerWorkspaceFeatureSettings = Field(
        default_factory=CustomerWorkspaceFeatureSettings,
        description="Feature flags for the customer portal.",
    )

    @model_validator(mode="after")
    def _set_workspace_features(self) -> Self:
        if self.feature_settings is not None:
            self.workspace_features = CustomerWorkspaceFeatureSettings(
                member_model_enabled=self.feature_settings.member_model_enabled,
            )
        return self


class CustomerWorkspaceData(Schema):
    """Schema of an workspace and related data for customer portal."""

    workspace: CustomerWorkspace
    shares: list[CustomerProduct]
