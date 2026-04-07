"""Customer-portal session service: OTP generation and token exchange.

Implements the customer-portal login flow: generates a time-limited
numeric OTP code, sends it via email, and exchanges a valid code for
a bearer session token.  Supports both email-based and direct-token
authentication modes.
"""

import secrets
import string
import uuid
from dataclasses import dataclass
from math import ceil

import structlog

from rapidly.config import settings
from rapidly.core.crypto import get_token_hash
from rapidly.core.utils import now_utc
from rapidly.customers.customer.queries import CustomerRepository
from rapidly.customers.customer_portal.queries.customer_session_code import (
    CustomerSessionCodeRepository,
)
from rapidly.customers.customer_session.actions import (
    customer_session as customer_session_service,
)
from rapidly.errors import RapidlyError
from rapidly.identity.member.queries import MemberRepository
from rapidly.identity.member_session.actions import (
    member_session as member_session_service,
)
from rapidly.messaging.email.react import render_email_template
from rapidly.messaging.email.sender import enqueue_email
from rapidly.messaging.email.types import (
    CustomerSessionCodeEmail,
    CustomerSessionCodeProps,
)
from rapidly.models import (
    CustomerSession,
    CustomerSessionCode,
    MemberSession,
    Workspace,
)
from rapidly.models.member import Member, MemberRole
from rapidly.platform.workspace.queries import WorkspaceRepository
from rapidly.postgres import AsyncSession

_log = structlog.get_logger()


@dataclass
class CustomerOption:
    """Minimal customer info for disambiguation."""

    id: uuid.UUID
    name: str | None


class CustomerSessionError(RapidlyError): ...


class WorkspaceDoesNotExist(CustomerSessionError):
    def __init__(self, workspace_id: uuid.UUID) -> None:
        self.workspace_id = workspace_id
        message = f"Workspace {workspace_id} does not exist."
        super().__init__(message)


class CustomerDoesNotExist(CustomerSessionError):
    def __init__(self, email: str, workspace: Workspace) -> None:
        self.email = email
        self.workspace = workspace
        message = (
            f"Customer does not exist for email {email} and workspace {workspace.id}."
        )
        super().__init__(message)


class CustomerSessionCodeInvalidOrExpired(CustomerSessionError):
    def __init__(self) -> None:
        super().__init__(
            "This customer session code is invalid or has expired.", status_code=401
        )


class CustomerSelectionRequired(CustomerSessionError):
    """Raised when multiple customers match the email and selection is needed."""

    def __init__(self, customers: list[CustomerOption]) -> None:
        self.customers = customers
        super().__init__(
            "Multiple customers found for this email. Please select one.",
            status_code=409,
        )


class CustomerSessionService:
    # ── Creation ──

    async def request(
        self,
        session: AsyncSession,
        email: str,
        workspace_id: uuid.UUID,
        customer_id: uuid.UUID | None = None,
    ) -> tuple[CustomerSessionCode, str]:
        workspace_repository = WorkspaceRepository.from_session(session)
        workspace = await workspace_repository.get_by_id(workspace_id)
        if workspace is None:
            raise WorkspaceDoesNotExist(workspace_id)

        member_model_enabled = workspace.feature_settings.get(
            "member_model_enabled", False
        )

        if member_model_enabled:
            customer_session_code, code = await self._request_with_member_lookup(
                session, email, workspace, customer_id
            )
        else:
            customer_session_code, code = await self._request_with_customer_lookup(
                session, email, workspace
            )

        session.add(customer_session_code)
        return customer_session_code, code

    async def _request_with_member_lookup(
        self,
        session: AsyncSession,
        email: str,
        workspace: Workspace,
        customer_id: uuid.UUID | None,
    ) -> tuple[CustomerSessionCode, str]:
        """
        Member-based lookup with disambiguation for migrated orgs.

        Used when member_model_enabled=true. Looks up members by email and
        handles the case where multiple members share the same email.
        """
        member_repository = MemberRepository.from_session(session)
        members = await member_repository.list_by_email_and_workspace(
            email, workspace.id
        )

        if not members:
            # Graceful fallback: if a customer exists with this email but has no
            # active member, auto-create an owner member for them.
            customer_repository = CustomerRepository.from_session(session)
            customer = await customer_repository.get_by_email_and_workspace(
                email, workspace.id
            )
            if customer is not None:
                # Check for soft-deleted member first and re-activate it
                deleted_members = await member_repository.list_by_email_and_workspace(
                    email, workspace.id, include_deleted=True
                )
                reactivated = None
                for dm in deleted_members:
                    if dm.deleted_at is not None and dm.customer_id == customer.id:
                        dm.deleted_at = None
                        dm.role = MemberRole.owner
                        session.add(dm)
                        await session.flush()
                        reactivated = dm
                        break

                if reactivated is not None:
                    reactivated.customer = customer
                    members = [reactivated]
                else:
                    new_member = Member(
                        customer_id=customer.id,
                        workspace_id=workspace.id,
                        email=email,
                        role=MemberRole.owner,
                    )
                    session.add(new_member)
                    await session.flush()
                    new_member.customer = customer
                    members = [new_member]
            else:
                raise CustomerDoesNotExist(email, workspace)

        if customer_id is not None:
            target_member = next(
                (m for m in members if m.customer_id == customer_id), None
            )
            if target_member is None:
                raise CustomerDoesNotExist(email, workspace)
            member = target_member
        elif len(members) == 1:
            member = members[0]
        else:
            customer_options = [
                CustomerOption(id=m.customer.id, name=m.customer.name) for m in members
            ]
            raise CustomerSelectionRequired(customer_options)

        code, code_hash = self._generate_code_hash()
        customer_session_code = CustomerSessionCode(
            code=code_hash, email=member.email, customer=member.customer
        )
        return customer_session_code, code

    async def _request_with_customer_lookup(
        self,
        session: AsyncSession,
        email: str,
        workspace: Workspace,
    ) -> tuple[CustomerSessionCode, str]:
        """
        Legacy customer-based lookup for non-migrated orgs.

        Used when member_model_enabled=false. Looks up customers directly
        by email since members don't exist for this workspace yet.
        """
        customer_repository = CustomerRepository.from_session(session)
        customer = await customer_repository.get_by_email_and_workspace(
            email, workspace.id
        )

        if customer is None:
            raise CustomerDoesNotExist(email, workspace)

        code, code_hash = self._generate_code_hash()
        customer_session_code = CustomerSessionCode(
            code=code_hash, email=email, customer=customer
        )
        return customer_session_code, code

    async def send(
        self,
        session: AsyncSession,
        customer_session_code: CustomerSessionCode,
        code: str,
    ) -> None:
        customer = customer_session_code.customer
        workspace_repository = WorkspaceRepository.from_session(session)
        workspace = await workspace_repository.get_by_id(
            customer_session_code.customer.workspace_id
        )
        if workspace is None:
            raise ValueError(
                f"Workspace {customer_session_code.customer.workspace_id} not found"
            )

        delta = customer_session_code.expires_at - now_utc()
        code_lifetime_minutes = int(ceil(delta.total_seconds() / 60))

        body = render_email_template(
            CustomerSessionCodeEmail(
                props=CustomerSessionCodeProps.model_validate(
                    {
                        "email": customer.email,
                        "workspace": workspace,
                        "code": code,
                        "code_lifetime_minutes": code_lifetime_minutes,
                        "url": settings.generate_frontend_url(
                            f"/{workspace.slug}/portal/authenticate"
                        ),
                    }
                )
            )
        )

        enqueue_email(
            **workspace.email_from_reply,
            to_email_addr=customer.email,
            subject=f"Access your {workspace.name} purchases",
            html_content=body,
        )

        if settings.is_development():
            _log.info(
                "\n"
                "╔══════════════════════════════════════════════════════════╗\n"
                "║                                                          ║\n"
                f"║           🔑 CUSTOMER SESSION CODE: {code}              ║\n"
                "║                                                          ║\n"
                "╚══════════════════════════════════════════════════════════╝"
            )

    # ── Token exchange ──

    async def authenticate(
        self, session: AsyncSession, code: str
    ) -> tuple[str, CustomerSession | MemberSession]:
        code_hash = get_token_hash(code, secret=settings.SECRET)

        code_repository = CustomerSessionCodeRepository.from_session(session)
        customer_session_code = await code_repository.get_valid_by_code_hash(code_hash)

        if customer_session_code is None:
            raise CustomerSessionCodeInvalidOrExpired()

        customer = customer_session_code.customer
        if customer_session_code.email.lower() == customer.email.lower():
            customer_repository = CustomerRepository.from_session(session)
            await customer_repository.update(
                customer, update_dict={"email_verified": True}
            )

        await session.delete(customer_session_code)

        workspace = customer.workspace

        # For orgs with member_model_enabled, create MemberSession instead
        if workspace.feature_settings.get("member_model_enabled", False):
            member_repository = MemberRepository.from_session(session)

            # Look up member by (customer, email) - unique combination
            member = await member_repository.get_by_customer_and_email(
                session, customer, customer_session_code.email
            )

            if member is None:
                # Member not found - code is no longer valid for this email
                raise CustomerSessionCodeInvalidOrExpired()

            # Use create_member_session directly (not create() which checks seat_based_pricing)
            return await member_session_service.create_member_session(session, member)

        # Legacy: create CustomerSession
        return await customer_session_service.create_customer_session(session, customer)

    # ── Cleanup ──

    def _generate_code_hash(self) -> tuple[str, str]:
        code = "".join(
            secrets.choice(string.ascii_uppercase + string.digits)
            for _ in range(settings.CUSTOMER_SESSION_CODE_LENGTH)
        )
        code_hash = get_token_hash(code, secret=settings.SECRET)
        return code, code_hash


customer_session = CustomerSessionService()
