"""Customer session lifecycle: code generation, token exchange, and cleanup.

Handles the two-step customer-portal authentication flow: a short-lived
numeric code is created (emailed or returned to the caller), then
exchanged for a bearer token.  Also supports direct token creation for
programmatic integrations and cascading member-session creation.
"""

import uuid

import structlog
from pydantic import HttpUrl
from sqlalchemy.orm import joinedload

from rapidly.config import settings
from rapidly.core.crypto import generate_token_hash_pair, get_token_hash
from rapidly.customers.customer.queries import CustomerRepository
from rapidly.enums import TokenType
from rapidly.errors import RequestValidationError, validation_error
from rapidly.identity.auth.models import AuthPrincipal, User, Workspace
from rapidly.identity.member.queries import MemberRepository
from rapidly.identity.member_session.actions import (
    member_session as member_session_service,
)
from rapidly.logging import Logger
from rapidly.models import Customer, CustomerSession, Member, MemberSession
from rapidly.models.customer import CustomerType
from rapidly.models.member import MemberRole
from rapidly.postgres import AsyncSession

from .queries import CustomerSessionRepository
from .types import CustomerSessionCreate, CustomerSessionCustomerIDCreate

_log: Logger = structlog.get_logger(__name__)

CUSTOMER_SESSION_TOKEN_PREFIX = "rapidly_cst_"


class CustomerSessionService:
    """Two-step portal auth: code generation, token exchange, and session cleanup."""

    # ── Creation ──

    async def create(
        self,
        session: AsyncSession,
        auth_subject: AuthPrincipal[User | Workspace],
        customer_create: CustomerSessionCreate,
    ) -> CustomerSession | MemberSession:
        repository = CustomerRepository.from_session(session)
        statement = repository.get_readable_statement(auth_subject).options(
            joinedload(Customer.workspace),
        )

        id_field: str
        id_value: uuid.UUID | str
        if isinstance(customer_create, CustomerSessionCustomerIDCreate):
            statement = statement.where(Customer.id == customer_create.customer_id)
            id_field = "customer_id"
            id_value = customer_create.customer_id
        else:
            statement = statement.where(
                Customer.external_id == customer_create.external_customer_id
            )
            id_field = "external_customer_id"
            id_value = customer_create.external_customer_id

        customer = await repository.get_one_or_none(statement)

        if customer is None:
            raise RequestValidationError(
                [validation_error(id_field, "Customer does not exist.", id_value)]
            )

        # For orgs with member_model_enabled, create MemberSession
        feature_settings = customer.workspace.feature_settings
        if feature_settings.get("member_model_enabled", False):
            member_repository = MemberRepository.from_session(session)

            # If a specific member was requested, look them up
            if customer_create.member_id is not None:
                member = await member_repository.get_by_id_and_customer_id(
                    customer_create.member_id, customer.id
                )
                if member is None:
                    raise RequestValidationError(
                        [
                            validation_error(
                                "member_id",
                                "Member does not exist.",
                                customer_create.member_id,
                            )
                        ]
                    )
                member.customer = customer
            elif customer_create.external_member_id is not None:
                member = await member_repository.get_by_customer_id_and_external_id(
                    customer.id, customer_create.external_member_id
                )
                if member is None:
                    raise RequestValidationError(
                        [
                            validation_error(
                                "external_member_id",
                                "Member does not exist.",
                                customer_create.external_member_id,
                            )
                        ]
                    )
                member.customer = customer
            elif customer.type == CustomerType.team:
                # Team customers require an explicit member_id
                raise RequestValidationError(
                    [
                        validation_error(
                            "member_id",
                            "member_id is required for team customers.",
                            None,
                        )
                    ]
                )
            else:
                # Individual customer: use or auto-create the owner member
                member = await member_repository.get_owner_by_customer_id(
                    session, customer.id
                )
                if member is None:
                    member = Member(
                        customer_id=customer.id,
                        workspace_id=customer.workspace_id,
                        email=customer.email,
                        name=customer.name or customer.email,
                        role=MemberRole.owner,
                    )
                    member_repository = MemberRepository.from_session(session)
                    await member_repository.create(member, flush=True)
                    member.customer = customer

            token, member_session = await member_session_service.create_member_session(
                session, member, customer_create.return_url
            )
            member_session.raw_token = token
            return member_session

        token, customer_session = await self.create_customer_session(
            session, customer, customer_create.return_url
        )
        customer_session.raw_token = token
        return customer_session

    async def create_customer_session(
        self,
        session: AsyncSession,
        customer: Customer,
        return_url: HttpUrl | None = None,
    ) -> tuple[str, CustomerSession]:
        token, token_hash = generate_token_hash_pair(
            secret=settings.SECRET, prefix=CUSTOMER_SESSION_TOKEN_PREFIX
        )
        customer_session = CustomerSession(
            token=token_hash,
            customer=customer,
            return_url=str(return_url) if return_url else None,
        )
        repo = CustomerSessionRepository.from_session(session)
        await repo.create(customer_session, flush=True)

        return token, customer_session

    # ── Token exchange ──

    async def get_by_token(
        self, session: AsyncSession, token: str, *, expired: bool = False
    ) -> CustomerSession | None:
        token_hash = get_token_hash(token, secret=settings.SECRET)
        repo = CustomerSessionRepository.from_session(session)
        return await repo.get_by_token_hash(token_hash, expired=expired)

    # ── Cleanup ──

    async def delete_expired(self, session: AsyncSession) -> None:
        repo = CustomerSessionRepository.from_session(session)
        await repo.delete_expired()

    async def revoke_leaked(
        self,
        session: AsyncSession,
        token: str,
        token_type: TokenType,
        *,
        notifier: str,
        url: str | None,
    ) -> bool:
        customer_session = await self.get_by_token(session, token)

        if customer_session is None:
            return False

        repo = CustomerSessionRepository.from_session(session)
        await repo.delete(customer_session)

        _log.info(
            "Revoke leaked customer session token",
            id=customer_session.id,
            notifier=notifier,
            url=url,
        )

        return True


customer_session = CustomerSessionService()
