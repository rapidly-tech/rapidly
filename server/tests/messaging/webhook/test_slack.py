"""Tests for ``rapidly/messaging/webhook/slack.py``.

Slack Block Kit payload branding. Two load-bearing surfaces:

- ``get_branded_slack_payload`` MUST append the brand context
  block AFTER caller-supplied blocks. Drift to prepend would
  push the brand row to the top and bury the actual message.
  Drift to "replace" would silently drop the caller's blocks.
- The brand context block format pinned: a ``context`` block
  with an ``image`` element (favicon) plus a ``mrkdwn`` text
  element (``Powered by Rapidly``). Slack's API REJECTS
  malformed Block Kit payloads with 400, so drift here would
  fail every webhook delivery.
"""

from __future__ import annotations

from typing import Any

from rapidly.messaging.webhook.slack import (
    _BRAND_CONTEXT_BLOCK,
    SlackPayload,
    get_branded_slack_payload,
)


class TestBrandContextBlock:
    def test_block_type_is_context(self) -> None:
        # Pin: ``context`` block type. Slack's Block Kit treats
        # ``context`` as a small footer-style row; drift to
        # ``section`` would render the brand at full height and
        # dominate the message.
        assert _BRAND_CONTEXT_BLOCK["type"] == "context"

    def test_has_image_then_mrkdwn(self) -> None:
        # Pin the element order: image first, then "Powered by
        # Rapidly" text. Drift would put the favicon AFTER the
        # text and visually misalign with Slack's footer
        # convention.
        elements = _BRAND_CONTEXT_BLOCK["elements"]
        assert elements[0]["type"] == "image"
        assert elements[1]["type"] == "mrkdwn"

    def test_image_has_favicon_url_and_alt(self) -> None:
        # Pin: alt_text "Rapidly" — accessibility requirement so
        # screen readers announce the brand instead of a
        # generic "image".
        from rapidly.config import settings

        img = _BRAND_CONTEXT_BLOCK["elements"][0]
        assert img["image_url"] == settings.FAVICON_URL
        assert img["alt_text"] == "Rapidly"

    def test_mrkdwn_text_pinned(self) -> None:
        # Pin the literal copy. Drift to "via Rapidly" or
        # similar would change brand presence and may silently
        # break customer-facing messaging guidelines.
        text_el = _BRAND_CONTEXT_BLOCK["elements"][1]
        assert text_el["text"] == "Powered by Rapidly"


class TestGetBrandedSlackPayload:
    def test_appends_brand_block_after_existing_blocks(self) -> None:
        # Pin: brand block goes AT THE END, not the start. Slack
        # renders blocks top-to-bottom so the user's message
        # content must appear before our footer.
        existing = {"type": "section", "text": {"type": "mrkdwn", "text": "hi"}}
        payload: SlackPayload = {"text": "x", "blocks": [existing]}
        result = get_branded_slack_payload(payload)
        assert result["blocks"][0] == existing
        assert result["blocks"][-1] == _BRAND_CONTEXT_BLOCK

    def test_handles_payload_without_blocks(self) -> None:
        # Pin: callers that emit ``text`` only (no rich blocks)
        # still get the brand row appended. Drift would lose
        # branding on the simplest webhook payloads.
        payload: SlackPayload = {"text": "hello world"}
        result = get_branded_slack_payload(payload)
        assert result["blocks"] == [_BRAND_CONTEXT_BLOCK]

    def test_preserves_text_field(self) -> None:
        # Pin: top-level ``text`` is the fallback rendered on
        # mobile push notifications + when blocks fail to render.
        # Drift would silently lose mobile push titles.
        payload: SlackPayload = {"text": "Customer signed up"}
        result = get_branded_slack_payload(payload)
        assert result["text"] == "Customer signed up"

    def test_does_not_mutate_input(self) -> None:
        # Pin: the input payload is NOT mutated. A regression to
        # ``payload["blocks"].append(...)`` would corrupt the
        # caller's blocks list across retries.
        existing = [{"type": "section"}]
        payload: SlackPayload = {"text": "x", "blocks": existing}
        get_branded_slack_payload(payload)
        # Caller's list still has exactly the one block.
        assert len(existing) == 1
        # And the caller's payload dict still has the same blocks.
        assert payload["blocks"] is existing

    def test_preserves_arbitrary_extra_fields(self) -> None:
        # Pin: ``**payload`` spread preserves caller-supplied
        # fields not declared in the TypedDict (e.g., future
        # Slack-API additions). Drift to a literal dict
        # construction would silently drop them.
        payload: dict[str, Any] = {
            "text": "x",
            "blocks": [],
            "thread_ts": "1234.5678",
        }
        result = get_branded_slack_payload(payload)  # type: ignore[arg-type]
        assert result["thread_ts"] == "1234.5678"  # type: ignore[typeddict-item]
