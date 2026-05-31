"""Endpoint-level privacy-hygiene tests for /login-code/request.

The action-layer tests (``test_service.py::TestRequestPrivacyHygiene``)
pin that the action runs the same way for known + unknown emails.
These tests pin the *public* HTTP contract — that the response
status code and body shape don't differ between the two cases.

Mirrors the customer_session endpoint tests
(``customer_portal/endpoints/test_customer_session.py``) which
already pin equivalent properties for that flow.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from httpx import AsyncClient
from pytest_mock import MockerFixture

from tests.fixtures.database import SaveFixture
from tests.fixtures.random_objects import create_user


@pytest.fixture(autouse=True)
def mock_send_email(mocker: MockerFixture) -> MagicMock:
    """Stub out the email-send so the test doesn't hit SMTP."""
    return mocker.patch(
        "rapidly.identity.login_code.api.login_code_service.send",
        autospec=True,
    )


@pytest.mark.asyncio
class TestRequestEndpointPrivacy:
    """The /login-code/request HTTP response MUST NOT differ
    between known + unknown email addresses. Otherwise an
    anonymous attacker can enumerate the user database via
    response-code / response-body comparison.

    Pinning the status code + (empty) body shape at the
    endpoint layer guards against a future refactor that
    returns 404 for unknown emails or adds a "user not
    found" key to the JSON body.
    """

    async def test_existing_user_returns_202(
        self,
        client: AsyncClient,
        save_fixture: SaveFixture,
    ) -> None:
        user = await create_user(save_fixture)
        user.email = "known@example.com"
        await save_fixture(user)

        response = await client.post(
            "/api/login-code/request",
            json={"email": "known@example.com"},
        )
        assert response.status_code == 202

    async def test_unknown_email_returns_202(
        self,
        client: AsyncClient,
    ) -> None:
        # Critical: same status code as the known-email path.
        # A future refactor that returns 404 for unknown would
        # leak existence.
        response = await client.post(
            "/api/login-code/request",
            json={"email": "stranger@example.com"},
        )
        assert response.status_code == 202

    async def test_response_body_identical_either_way(
        self,
        client: AsyncClient,
        save_fixture: SaveFixture,
    ) -> None:
        user = await create_user(save_fixture)
        user.email = "real@example.com"
        await save_fixture(user)

        known = await client.post(
            "/api/login-code/request",
            json={"email": "real@example.com"},
        )
        unknown = await client.post(
            "/api/login-code/request",
            json={"email": "ghost@example.com"},
        )

        # Both responses have the same body. The 202 contract is
        # "no body" — text() is empty in both cases. A future
        # refactor that adds an "exists: true/false" field would
        # fail this assertion loudly.
        assert known.text == unknown.text
        # Both are 202 (re-asserting here so this test stays
        # self-contained if the per-case tests above get split out).
        assert known.status_code == 202
        assert unknown.status_code == 202

    async def test_send_email_called_for_both_paths(
        self,
        client: AsyncClient,
        save_fixture: SaveFixture,
        mock_send_email: MagicMock,
    ) -> None:
        """The email-send side effect fires for both known + unknown
        addresses. Without this, the request-vs-no-op latency
        difference would leak existence (the known path sends an
        email; the unknown path would be measurably faster)."""
        user = await create_user(save_fixture)
        user.email = "yes@example.com"
        await save_fixture(user)

        await client.post(
            "/api/login-code/request",
            json={"email": "yes@example.com"},
        )
        await client.post(
            "/api/login-code/request",
            json={"email": "no@example.com"},
        )

        # send() is called twice — once per request, known or not.
        # If a future refactor short-circuits the unknown path,
        # this assertion fails.
        assert mock_send_email.call_count == 2
