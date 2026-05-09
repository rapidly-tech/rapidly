"""Slack Block Kit payload construction for webhook delivery.

Builds branded Slack message payloads using Block Kit, appending a
Rapidly-branded context block to every outgoing message.
"""

from typing import Any, Literal, NotRequired, TypedDict

from rapidly.config import settings

# ---------------------------------------------------------------------------
# Block Kit type stubs
# ---------------------------------------------------------------------------


class SlackText(TypedDict):
    type: Literal["mrkdwn", "plain_text"]
    text: str
    emoji: NotRequired[bool]
    verbatim: NotRequired[bool]


class SlackPayload(TypedDict):
    text: str
    blocks: NotRequired[list[dict[str, Any]]]


# ---------------------------------------------------------------------------
# Branding
# ---------------------------------------------------------------------------

_BRAND_CONTEXT_BLOCK: dict[str, Any] = {
    "type": "context",
    "elements": [
        {
            "type": "image",
            "image_url": settings.FAVICON_URL,
            "alt_text": "Rapidly",
        },
        {"type": "mrkdwn", "text": "Powered by Rapidly"},
    ],
}


def get_branded_slack_payload(payload: SlackPayload) -> SlackPayload:
    existing_blocks = payload.get("blocks", [])
    return {
        **payload,
        "blocks": [*existing_blocks, _BRAND_CONTEXT_BLOCK],
    }
