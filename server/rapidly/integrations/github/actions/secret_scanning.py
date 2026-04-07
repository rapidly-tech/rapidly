"""GitHub secret-scanning partnership: leaked token detection and revocation.

Verifies the ECDSA signature on incoming secret-scanning alerts,
identifies the leaked token type, revokes it, and notifies the
affected user or workspace.
"""

import base64
import binascii
from typing import Annotated, Any, Literal, Protocol, TypedDict

from cryptography.exceptions import InvalidSignature as CryptographyInvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from fastapi.exceptions import RequestValidationError
from pydantic import BeforeValidator, TypeAdapter, ValidationError

from rapidly.core.types import Schema
from rapidly.customers.customer_session.actions import (
    customer_session as customer_session_service,
)
from rapidly.enums import TokenType
from rapidly.errors import RapidlyError
from rapidly.identity.auth import actions as auth_service
from rapidly.identity.oauth2.actions.oauth2_authorization_code import (
    oauth2_authorization_code as oauth2_authorization_code_service,
)
from rapidly.identity.oauth2.actions.oauth2_client import (
    oauth2_client as oauth2_client_service,
)
from rapidly.identity.oauth2.actions.oauth2_token import (
    oauth2_token as oauth2_token_service,
)
from rapidly.platform.workspace_access_token import (
    actions as workspace_access_token_service,
)
from rapidly.postgres import AsyncSession

from ..client import GitHub

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------


class GitHubSecretScanningPublicKey(TypedDict):
    key_identifier: str
    key: str
    is_current: bool


class GitHubSecretScanningPublicKeyList(TypedDict):
    public_keys: list[GitHubSecretScanningPublicKey]


def _normalize_token_type(value: Any | None) -> Any | None:
    if isinstance(value, str):
        return value.lower()
    return value


class GitHubSecretScanningToken(Schema):
    token: str
    type: Annotated[TokenType, BeforeValidator(_normalize_token_type)]
    url: str | None = None
    source: str


GitHubSecretScanningTokenListAdapter = TypeAdapter(list[GitHubSecretScanningToken])


class GitHubSecretScanningTokenResult(TypedDict):
    token_raw: str
    token_type: TokenType
    label: Literal["true_positive", "false_positive"]


class RevokedLeakedProtocol(Protocol):
    async def revoke_leaked(
        self,
        session: AsyncSession,
        token: str,
        token_type: TokenType,
        *,
        notifier: str,
        url: str | None,
    ) -> bool: ...


# ---------------------------------------------------------------------------
# Token type -> service mapping
# ---------------------------------------------------------------------------

TOKEN_TYPE_SERVICE_MAP: dict[TokenType, RevokedLeakedProtocol] = {
    TokenType.client_secret: oauth2_client_service,
    TokenType.client_registration_token: oauth2_client_service,
    TokenType.authorization_code: oauth2_authorization_code_service,
    TokenType.access_token: oauth2_token_service,
    TokenType.refresh_token: oauth2_token_service,
    TokenType.workspace_access_token: workspace_access_token_service,
    TokenType.customer_session_token: customer_session_service,
    TokenType.user_session_token: auth_service,
}


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class GitHubSecretScanningError(RapidlyError): ...


class PublicKeyNotFound(GitHubSecretScanningError):
    def __init__(self, key_identifier: str) -> None:
        self.key_identifier = key_identifier
        super().__init__(
            f"Public key with key_identifier {key_identifier} not found.", 400
        )


class InvalidPublicKey(GitHubSecretScanningError):
    def __init__(self, key_identifier: str, public_key: str) -> None:
        self.key_identifier = key_identifier
        self.public_key = public_key
        super().__init__(f"Public key with key_identifier {key_identifier} is invalid.")


class InvalidSignature(GitHubSecretScanningError):
    def __init__(self, payload: str, signature: str, key_identifier: str) -> None:
        self.payload = payload
        self.signature = signature
        self.key_identifier = key_identifier
        super().__init__("Invalid signature.", status_code=403)


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class GitHubSecretScanningService:
    # ------------------------------------------------------------------
    # Alert processing
    # ------------------------------------------------------------------

    async def handle_alert(
        self, session: AsyncSession, data: list[GitHubSecretScanningToken]
    ) -> list[GitHubSecretScanningTokenResult]:
        outcomes: list[GitHubSecretScanningTokenResult] = []
        for match in data:
            result = await self._process_token(session, match)
            outcomes.append(result)
        return outcomes

    def validate_payload(self, payload: str) -> list[GitHubSecretScanningToken]:
        try:
            return GitHubSecretScanningTokenListAdapter.validate_json(payload)
        except ValidationError as exc:
            raise RequestValidationError(exc.errors(), body=payload)

    # ------------------------------------------------------------------
    # Signature verification
    # ------------------------------------------------------------------

    async def verify_signature(
        self, payload: str, signature: str, key_identifier: str
    ) -> bool:
        raw_key = await self._fetch_public_key(key_identifier)
        pub_key = load_pem_public_key(raw_key.encode())
        if not isinstance(pub_key, ec.EllipticCurvePublicKey):
            raise InvalidPublicKey(key_identifier, raw_key)

        try:
            sig_bytes = base64.b64decode(signature)
            pub_key.verify(sig_bytes, payload.encode(), ec.ECDSA(hashes.SHA256()))
            return True
        except (binascii.Error, CryptographyInvalidSignature) as exc:
            raise InvalidSignature(payload, signature, key_identifier) from exc

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _process_token(
        self, session: AsyncSession, match: GitHubSecretScanningToken
    ) -> GitHubSecretScanningTokenResult:
        handler = TOKEN_TYPE_SERVICE_MAP.get(match.type)
        if handler is None:
            return {
                "token_raw": match.token,
                "token_type": match.type,
                "label": "false_positive",
            }

        was_leaked = await handler.revoke_leaked(
            session, match.token, match.type, notifier="github", url=match.url
        )

        return {
            "token_raw": match.token,
            "token_type": match.type,
            "label": "true_positive" if was_leaked else "false_positive",
        }

    async def _fetch_public_key(self, key_identifier: str) -> str:
        gh = GitHub()
        resp = await gh.arequest("GET", "/meta/public_keys/secret_scanning")

        key_list: GitHubSecretScanningPublicKeyList = resp.json()
        for entry in key_list["public_keys"]:
            if entry["key_identifier"] == key_identifier:
                return entry["key"]

        raise PublicKeyNotFound(key_identifier)


secret_scanning = GitHubSecretScanningService()
