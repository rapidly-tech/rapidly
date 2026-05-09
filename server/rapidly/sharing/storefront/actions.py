"""Storefront service: public share listing for workspace profiles.

Provides read-only queries for the public-facing storefront, returning
visible products filtered by workspace slug and billing type.
"""

from collections.abc import Sequence
from typing import Any
from uuid import UUID

from rapidly.core.pagination import PaginationParams
from rapidly.models import Customer, Workspace
from rapidly.models.file_share_session import FileShareSession
from rapidly.postgres import AsyncReadSession
from rapidly.redis import Redis
from rapidly.sharing.file_sharing.queries import SecretRepository
from rapidly.sharing.storefront.queries import StorefrontRepository
from rapidly.sharing.storefront.types import (
    SecretStorefront,
    Storefront,
    StorefrontCustomer,
    StorefrontCustomers,
)


async def get(session: AsyncReadSession, slug: str) -> Workspace | None:
    repo = StorefrontRepository.from_session(session)
    return await repo.get_by_slug(slug)


async def list_public_file_shares(
    session: AsyncReadSession, workspace_id: UUID
) -> Sequence[FileShareSession]:
    """List active paid file shares for an workspace's public page."""
    repo = StorefrontRepository.from_session(session)
    return await repo.list_public_file_shares(workspace_id)


async def list_paid_secrets(redis: Redis, workspace_id: UUID) -> list[dict[str, Any]]:
    """List active paid secrets for a workspace's storefront."""
    repo = SecretRepository(redis)
    return await repo.list_paid_secrets(str(workspace_id))


async def list_customers(
    session: AsyncReadSession,
    workspace: Workspace,
    *,
    pagination: PaginationParams,
) -> tuple[Sequence[Customer], int]:
    repo = StorefrontRepository.from_session(session)
    return await repo.list_customers(workspace, pagination=pagination)


async def get_storefront(
    session: AsyncReadSession,
    slug: str,
    *,
    redis: Redis | None = None,
) -> Storefront | None:
    """Build a complete storefront view for a workspace slug."""
    workspace = await get(session, slug)
    if workspace is None:
        return None

    file_shares = await list_public_file_shares(session, workspace.id)
    customers, total = await list_customers(
        session, workspace, pagination=PaginationParams(1, 3)
    )

    # Fetch paid secrets from Redis if available
    secrets: list[SecretStorefront] = []
    if redis is not None:
        raw_secrets = await list_paid_secrets(redis, workspace.id)
        secrets = [SecretStorefront.model_validate(s) for s in raw_secrets]

    return Storefront.model_validate(
        {
            "workspace": workspace,
            "file_shares": file_shares,
            "secrets": secrets,
            "customers": StorefrontCustomers(
                total=total,
                customers=[
                    StorefrontCustomer(
                        name=customer.name[0] if customer.name else customer.email[0],
                    )
                    for customer in customers
                ],
            ),
        }
    )
