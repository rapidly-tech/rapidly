"""OAuth2 test fixtures using a synchronous database session.

The OAuth2 authorization server operates synchronously, so these fixtures
maintain a separate sync session.  Objects saved here are invisible to the
async session used by the rest of the test suite — see the save_fixture
override below for details.
"""

import os
from collections.abc import Iterator
from typing import Literal, cast

import pytest
from authlib.oauth2.rfc7636 import create_s256_code_challenge

from rapidly.app import app
from rapidly.config import settings
from rapidly.core.crypto import get_token_hash
from rapidly.core.db.postgres import Engine, Session, create_sync_engine
from rapidly.identity.oauth2.authorization_server import AuthorizationServer
from rapidly.identity.oauth2.dependencies import get_authorization_server
from rapidly.identity.oauth2.sub_type import SubType
from rapidly.models import (
    Model,
    OAuth2AuthorizationCode,
    OAuth2Client,
    OAuth2Token,
    User,
    Workspace,
)
from tests.fixtures.database import SaveFixture, get_database_url

# ── Sync database session ──


@pytest.fixture(scope="package", autouse=True)
def authlib_insecure_transport() -> None:
    os.environ["AUTHLIB_INSECURE_TRANSPORT"] = "true"


@pytest.fixture(scope="package")
def sync_engine(worker_id: str) -> Iterator[Engine]:
    engine = create_sync_engine(
        dsn=get_database_url(worker_id, driver="psycopg2"),
        application_name=f"test_sync_{worker_id}",
        pool_size=settings.DATABASE_POOL_SIZE,
        pool_recycle=settings.DATABASE_POOL_RECYCLE_SECONDS,
    )
    yield engine
    engine.dispose()


@pytest.fixture
def sync_session(sync_engine: Engine) -> Iterator[Session]:
    connection = sync_engine.connect()
    transaction = connection.begin()

    session = Session(bind=connection, expire_on_commit=False)

    yield session

    transaction.rollback()
    connection.close()


@pytest.fixture
def save_fixture(sync_session: Session) -> SaveFixture:
    """
    Override locally save_fixture to use the synchronous session.

    This is necessary because the OAuth2 features rely on the synchronous session.

    🚨 As such, objects won't be present in the async session. Code that works with
    the async session won't be able to see the objects saved by this fixture.

    🧠 You might be tempted to save the object in the async session as well.
    This **won't** work. Underneath, there are two different connections
    and transactions to the database; so you'll end up with conflicts or locks.
    😢 Time lost on this: 4 hours.
    """

    async def _save_fixture(model: Model) -> None:
        sync_session.add(model)
        sync_session.flush()
        sync_session.expunge(model)

    return _save_fixture


@pytest.fixture(autouse=True)
def override_get_authorization_server(sync_session: Session) -> Iterator[None]:
    authorization_server = AuthorizationServer.build(sync_session)
    app.dependency_overrides[get_authorization_server] = lambda: authorization_server
    yield
    app.dependency_overrides.pop(get_authorization_server)


# ── Token & authorization code factories ──


async def create_oauth2_token(
    save_fixture: SaveFixture,
    *,
    client: OAuth2Client,
    access_token: str,
    refresh_token: str,
    scopes: list[str],
    user: User | None = None,
    workspace: Workspace | None = None,
    access_token_revoked_at: int | None = None,
    refresh_token_revoked_at: int | None = None,
) -> OAuth2Token:
    token = OAuth2Token(
        client_id=client.client_id,
        token_type="bearer",
        access_token=get_token_hash(access_token, secret=settings.SECRET),
        refresh_token=get_token_hash(refresh_token, secret=settings.SECRET),
        scope=" ".join(scopes),
        access_token_revoked_at=access_token_revoked_at,
        refresh_token_revoked_at=refresh_token_revoked_at,
    )
    if user is not None:
        token.user_id = user.id
        token.sub_type = SubType.user
    if workspace is not None:
        token.workspace_id = workspace.id
        token.sub_type = SubType.workspace
    await save_fixture(token)
    return token


async def create_oauth2_authorization_code(
    save_fixture: SaveFixture,
    *,
    client: OAuth2Client,
    code: str,
    scopes: list[str],
    redirect_uri: str,
    user: User | None = None,
    workspace: Workspace | None = None,
    code_verifier: str | None = None,
    code_challenge_method: Literal["plain", "S256"] | None = None,
) -> OAuth2AuthorizationCode:
    authorization_code = OAuth2AuthorizationCode(
        code=get_token_hash(code, secret=settings.SECRET),
        client_id=client.client_id,
        scope=" ".join(scopes),
        redirect_uri=redirect_uri,
    )
    if code_challenge_method is not None:
        assert code_verifier is not None, "code_verifier must be provided"
        authorization_code.code_challenge_method = code_challenge_method  # pyright: ignore
        authorization_code.code_challenge = cast(  # pyright: ignore
            str,
            (
                create_s256_code_challenge(code_verifier)
                if code_challenge_method == "S256"
                else code_verifier
            ),
        )
    if user is not None:
        authorization_code.user_id = user.id
        authorization_code.sub_type = SubType.user
    if workspace is not None:
        authorization_code.workspace_id = workspace.id
        authorization_code.sub_type = SubType.workspace
    await save_fixture(authorization_code)
    return authorization_code
