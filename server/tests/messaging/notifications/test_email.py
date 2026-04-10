"""Tests for email notification delivery."""

import inspect
import os

import pytest

from rapidly.messaging.notifications.notification import (
    NotificationPayloadBase,
    WorkspaceCreateAccountNotificationPayload,
)


async def check_diff(email: tuple[str, str]) -> None:
    (subject, body) = email
    expected = f"{subject}\n<hr>\n{body}"

    # Run with `RAPIDLY_TEST_RECORD=1 pytest` to produce new golden files :-)
    record = os.environ.get("RAPIDLY_TEST_RECORD", False) == "1"

    name = inspect.stack()[1].function

    if record:
        with open(f"./tests/notifications/testdata/{name}.html", "w") as f:
            f.write(expected)
            return
    else:
        with open(f"./tests/notifications/testdata/{name}.html") as f:
            content = f.read()

    assert content == expected


@pytest.mark.asyncio
async def test_WorkspaceCreateAccountNotificationPayload() -> None:
    n = WorkspaceCreateAccountNotificationPayload(
        workspace_name="orgname",
        url="https://example.com/url",
    )

    await check_diff(n.render())


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        WorkspaceCreateAccountNotificationPayload(
            workspace_name="{{ 123456 * 9 }}",
            url="https://example.com/url",
        ),
    ],
)
async def test_injection_payloads(payload: NotificationPayloadBase) -> None:
    subject, body = payload.render()
    # The template expression must NOT be evaluated
    assert str(123456 * 9) not in subject
    assert str(123456 * 9) not in body
