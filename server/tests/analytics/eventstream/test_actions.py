"""Tests for ``rapidly/analytics/eventstream/actions.py`` — the
pub/sub plumbing that backs the SSE dashboard event stream.

Pins the channel-naming contract (``<scope>:<id>``) and the fan-out
semantics of ``send_event`` (publishes to every supplied channel with
the exact payload).
"""

from __future__ import annotations

import uuid

import pytest

from rapidly.analytics.eventstream.actions import Event, Receivers, send_event
from rapidly.redis import Redis


class TestReceiversChannelGeneration:
    def test_generate_channel_name_uses_colon_separator(self) -> None:
        r = Receivers()
        uid = uuid.UUID("11111111-1111-1111-1111-111111111111")
        assert r.generate_channel_name("user", uid) == f"user:{uid}"

    def test_empty_Receivers_produces_no_channels(self) -> None:
        # No subscriber IDs → no channels to publish on.
        assert Receivers().get_channels() == []

    def test_user_only_produces_one_user_channel(self) -> None:
        uid = uuid.uuid4()
        channels = Receivers(user_id=uid).get_channels()
        assert channels == [f"user:{uid}"]

    def test_workspace_id_uses_org_prefix_not_workspace(self) -> None:
        # Pinning the prefix: the DB column is ``workspace_id`` but the
        # historic channel-name prefix is ``org:`` (the platform was
        # renamed workspace → org → workspace). Subscribers key on
        # the ``org:`` prefix.
        oid = uuid.uuid4()
        channels = Receivers(workspace_id=oid).get_channels()
        assert channels == [f"org:{oid}"]

    def test_customer_id_uses_customer_prefix(self) -> None:
        cid = uuid.uuid4()
        assert Receivers(customer_id=cid).get_channels() == [f"customer:{cid}"]

    def test_all_three_ids_produce_three_channels_in_documented_order(
        self,
    ) -> None:
        # ``user`` → ``org`` → ``customer`` order pinned (matches the
        # order the method appends them). Subscribers may depend on
        # ordering for prioritisation.
        user = uuid.uuid4()
        org = uuid.uuid4()
        cust = uuid.uuid4()
        channels = Receivers(
            user_id=user, workspace_id=org, customer_id=cust
        ).get_channels()
        assert channels == [
            f"user:{user}",
            f"org:{org}",
            f"customer:{cust}",
        ]


class TestEventModel:
    def test_roundtrips_through_pydantic_serialisation(self) -> None:
        # Defensive pin — the Event schema is the wire contract for
        # the SSE payload.
        e = Event(
            id=uuid.UUID("22222222-2222-2222-2222-222222222222"),
            key="customer.created",
            payload={"customer_id": "abc"},
        )
        dumped = e.model_dump()
        assert dumped["id"] == e.id
        assert dumped["key"] == "customer.created"
        assert dumped["payload"] == {"customer_id": "abc"}


@pytest.mark.asyncio
class TestSendEvent:
    async def test_publishes_to_every_supplied_channel(self, redis: Redis) -> None:
        # Subscribe to two channels using a pubsub connection, fire
        # ``send_event`` across both, and verify both get the same
        # serialised payload.
        pubsub = redis.pubsub()
        await pubsub.subscribe("user:alice", "customer:bob")
        # Drain the initial subscription-confirmation messages.
        for _ in range(2):
            await pubsub.get_message(ignore_subscribe_messages=True, timeout=1)

        await send_event(redis, '{"hello":"world"}', ["user:alice", "customer:bob"])

        received: list[tuple[str, str]] = []
        for _ in range(2):
            msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1)
            assert msg is not None
            channel = msg["channel"]
            data = msg["data"]
            received.append(
                (
                    channel.decode() if isinstance(channel, bytes) else channel,
                    data.decode() if isinstance(data, bytes) else data,
                )
            )
        await pubsub.unsubscribe()
        await pubsub.close()

        assert sorted(received) == sorted(
            [
                ("user:alice", '{"hello":"world"}'),
                ("customer:bob", '{"hello":"world"}'),
            ]
        )

    async def test_empty_channels_list_is_noop(self, redis: Redis) -> None:
        # Zero channels → zero publishes; must not raise.
        await send_event(redis, '{"x":1}', [])

    async def test_payload_is_sent_verbatim(self, redis: Redis) -> None:
        # The helper does NO serialisation — callers are responsible
        # for passing a pre-serialised JSON string. Pinned so a
        # refactor that "helpfully" json.dumps'es the payload would
        # double-encode it.
        pubsub = redis.pubsub()
        await pubsub.subscribe("probe")
        await pubsub.get_message(ignore_subscribe_messages=True, timeout=1)

        raw_string = "not-json-at-all"
        await send_event(redis, raw_string, ["probe"])

        msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1)
        assert msg is not None
        data = msg["data"]
        assert (data.decode() if isinstance(data, bytes) else data) == raw_string
        await pubsub.unsubscribe()
        await pubsub.close()
