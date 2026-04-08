"""Member-session lifecycle service: creation, look-up, and cleanup.

Generates member-portal bearer tokens, links them to the parent
customer session, and manages session expiry and revocation.
"""

import structlog
from pydantic import HttpUrl
from sqlalchemy.orm import joinedload

from rapidly.config import settings
from rapidly.core.crypto import generate_token_hash_pair, get_token_hash
from rapidly.errors import NotPermitted, RequestValidationError, validation_error
from rapidly.identity.auth.models import AuthPrincipal, User, Workspace
from rapidly.identity.member.queries import MemberRepository
from rapidly.logging import Logger
from rapidly.models import Customer, Member, MemberSession
from rapidly.models.member_session import MEMBER_SESSION_TOKEN_PREFIX
from rapidly.models.workspace import Workspace as WorkspaceModel
from rapidly.postgres import AsyncSession

from .queries import MemberSessionRepository
from .types import MemberSessionCreate

_log: Logger = structlog.get_logger()


class MemberSessionService:
    """Bearer-token lifecycle for member-portal sessions."""

    # ── Creation ──

    async def create(
        self,
        session: AsyncSession,
        auth_subject: AuthPrincipal[User | Workspace],
        member_session_create: MemberSessionCreate,
    ) -> MemberSession:
        repository = MemberRepository.from_session(session)
        statement = (
            repository.get_readable_statement(auth_subject)
            .where(Member.id == member_session_create.member_id)
            .options(
                joinedload(Member.customer).joinedload(Customer.workspace),
            )
        )

        member = await repository.get_one_or_none(statement)

        if member is None:
            raise RequestValidationError(
                [
                    validation_error(
                        "member_id",
                        "Member does not exist.",
                        member_session_create.member_id,
                    )
                ]
            )

        workspace: WorkspaceModel = member.customer.workspace

        required_flags = ["member_model_enabled", "seat_based_pricing_enabled"]
        missing_flags = [
            flag
            for flag in required_flags
            if not workspace.feature_settings.get(flag, False)
        ]
        if missing_flags:
            raise NotPermitted(
                f"Member sessions require {', '.join(missing_flags)} to be enabled "
                "for the workspace. Use customer sessions instead."
            )

        token, member_session = await self.create_member_session(
            session, member, member_session_create.return_url
        )
        member_session.raw_token = token
        return member_session

    async def create_member_session(
        self,
        session: AsyncSession,
        member: Member,
        return_url: HttpUrl | None = None,
    ) -> tuple[str, MemberSession]:
        token, token_hash = generate_token_hash_pair(
            secret=settings.SECRET, prefix=MEMBER_SESSION_TOKEN_PREFIX
        )
        member_session = MemberSession(
            token=token_hash,
            member=member,
            return_url=str(return_url) if return_url else None,
        )
        repo = MemberSessionRepository.from_session(session)
        await repo.create(member_session, flush=True)

        return token, member_session

    # ── Token exchange ──

    async def get_by_token(
        self, session: AsyncSession, token: str, *, expired: bool = False
    ) -> MemberSession | None:
        token_hash = get_token_hash(token, secret=settings.SECRET)
        repository = MemberSessionRepository.from_session(session)
        return await repository.get_by_token_hash(token_hash, expired=expired)

    # ── Cleanup ──

    async def delete_expired(self, session: AsyncSession) -> None:
        repository = MemberSessionRepository.from_session(session)
        await repository.delete_expired()


member_session = MemberSessionService()
