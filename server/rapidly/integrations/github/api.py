"""GitHub secret-scanning webhook.

Handles the secret-scanning partnership endpoint for leaked token
alerts from GitHub.  Login and account-linking flows have moved to
the Microsoft integration (``integrations.microsoft``).
"""

from fastapi import Depends, Header, Request
from fastapi.responses import JSONResponse

from rapidly.openapi import APITag
from rapidly.postgres import AsyncSession, get_db_session
from rapidly.routing import APIRouter

from .actions.secret_scanning import secret_scanning as secret_scanning_service

# ---------------------------------------------------------------------------
# Top-level router
# ---------------------------------------------------------------------------

router = APIRouter(
    prefix="/integrations/github", tags=["integrations_github", APITag.private]
)


@router.post("/secret-scanning", include_in_schema=False)
async def secret_scanning(
    request: Request,
    github_public_key_identifier: str = Header(),
    github_public_key_signature: str = Header(),
    session: AsyncSession = Depends(get_db_session),
) -> JSONResponse:
    raw_body = (await request.body()).decode()
    await secret_scanning_service.verify_signature(
        raw_body, github_public_key_signature, github_public_key_identifier
    )

    tokens = secret_scanning_service.validate_payload(raw_body)
    outcomes = await secret_scanning_service.handle_alert(session, tokens)
    return JSONResponse(content=outcomes)
