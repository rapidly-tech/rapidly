"""First-party web-session grant for dashboard authentication.

A non-standard OAuth2 grant type (``grant_type=web``) that lets the
Rapidly dashboard exchange a cookie-backed session token for a
short-lived access token.  Only first-party clients with the ``web``
grant type configured may use this flow.
"""

import uuid
from collections.abc import Iterable
from typing import Any

from authlib.oauth2.rfc6749 import ClientMixin
from authlib.oauth2.rfc6749.errors import (
    InvalidGrantError,
    InvalidRequestError,
    UnauthorizedClientError,
)
from authlib.oauth2.rfc6749.grants import BaseGrant, TokenEndpointMixin
from authlib.oauth2.rfc6749.hooks import hooked
from sqlalchemy import and_, select

from rapidly.config import settings
from rapidly.core.crypto import get_token_hash
from rapidly.core.utils import now_utc
from rapidly.models import User, UserSession, Workspace, WorkspaceMembership

from ..sub_type import SubType, SubTypeValue


class WebGrant(BaseGrant, TokenEndpointMixin):
    """Exchange a member-session cookie for a short-lived access token."""

    GRANT_TYPE = "web"
    TOKEN_ENDPOINT_AUTH_METHODS = ["client_secret_basic", "client_secret_post"]

    def validate_token_request(self) -> None:
        authenticated_client = self._verify_client()
        self.request.client = authenticated_client
        resolved_subject = self._verify_session_token(authenticated_client)
        self.request.user = resolved_subject

    @hooked
    def create_token_response(self) -> tuple[int, Any, Iterable[tuple[str, str]]]:
        client = self.request.client
        subject = self.request.user
        effective_scope = self.request.payload.scope or client.scope
        token = self.generate_token(
            user=subject, scope=effective_scope, include_refresh_token=False
        )
        self.save_token(token)
        return 200, token, self.TOKEN_RESPONSE_HEADER

    # -- Client validation --

    def _verify_client(self) -> ClientMixin:
        """Authenticate the client and confirm the ``web`` grant is allowed."""
        client = self.authenticate_token_endpoint_client()
        if not client.check_grant_type(self.GRANT_TYPE):
            raise UnauthorizedClientError(
                f"The client is not authorized to use 'grant_type={self.GRANT_TYPE}'"
            )
        return client

    # -- Session + subject validation --

    def _verify_session_token(self, client: ClientMixin) -> SubTypeValue:
        """Validate the session token and resolve the target subject."""
        payload = self.request.payload
        if payload is None:
            raise InvalidRequestError("Missing request payload.")
        fields = payload.data

        raw_token = fields.get("session_token")
        if raw_token is None:
            raise InvalidRequestError("Missing 'session_token' in request.")

        # Parse sub_type
        raw_sub_type: str | None = fields.get("sub_type")
        try:
            parsed_sub_type = SubType(raw_sub_type) if raw_sub_type else SubType.user
        except ValueError as exc:
            raise InvalidRequestError("Invalid sub_type") from exc

        # Validate sub parameter presence
        raw_sub: str | None = fields.get("sub")
        if parsed_sub_type == SubType.workspace and raw_sub is None:
            raise InvalidRequestError("Missing 'sub' for workspace sub_type")
        if parsed_sub_type == SubType.user and raw_sub is not None:
            raise InvalidRequestError("Can't specify 'sub' for user sub_type")

        # Validate requested scope
        requested_scope = fields.get("scope", "")
        if requested_scope:
            self.server.validate_requested_scope(requested_scope)

        # Look up the session
        session_hash = get_token_hash(raw_token, secret=settings.SECRET)
        stmt = select(UserSession).where(
            UserSession.token == session_hash,
            UserSession.expires_at > now_utc(),
        )
        session_record: UserSession | None = (
            self.server.session.execute(stmt).unique().scalar_one_or_none()
        )
        if session_record is None:
            raise InvalidGrantError()

        # Resolve the subject
        return self._resolve_subject(parsed_sub_type, raw_sub, session_record.user)

    def _resolve_subject(
        self, sub_type: SubType, raw_sub: str | None, user: User
    ) -> SubTypeValue:
        """Map the validated parameters to a concrete (sub_type, subject) pair."""
        if sub_type == SubType.user:
            return sub_type, user

        if sub_type == SubType.workspace:
            assert raw_sub is not None
            try:
                ws_id = uuid.UUID(raw_sub)
            except ValueError as exc:
                raise InvalidRequestError("Invalid 'sub' UUID") from exc
            workspace = self._lookup_workspace_membership(ws_id, user)
            if workspace is None:
                raise InvalidGrantError()
            return sub_type, workspace

        raise InvalidRequestError(f"Unsupported sub_type: {sub_type}")

    def _lookup_workspace_membership(
        self, workspace_id: uuid.UUID, user: User
    ) -> Workspace | None:
        """Return the workspace if the user holds an active membership."""
        stmt = (
            select(Workspace)
            .join(
                WorkspaceMembership,
                onclause=and_(
                    WorkspaceMembership.user_id == user.id,
                    WorkspaceMembership.deleted_at.is_(None),
                ),
            )
            .where(Workspace.id == workspace_id)
        )
        return self.server.session.execute(stmt).unique().scalar_one_or_none()
