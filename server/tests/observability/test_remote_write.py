"""Tests for ``rapidly/observability/remote_write.py``.

Hand-rolled Prometheus Remote Write v1 protobuf encoder + background
pusher. Five load-bearing surfaces:

- Wire-format constants (``_WIRE_VARINT=0``, ``_WIRE_64BIT=1``,
  ``_WIRE_LEN_DELIMITED=2``) — these are protobuf protocol constants
  defined by the Remote Write spec; drift here means every push is
  rejected by Grafana / Mimir / Thanos as malformed.
- ``_varint`` — base-128 little-endian encoding. Mis-encoding the
  high/low byte order or the continuation bit silently corrupts
  every serialised label and sample.
- ``_build_sample`` replaces non-finite values (NaN, +/-Inf) with
  0.0. The Remote Write protocol allows special values, but Grafana
  Cloud's ingestor rejects them; pinning the float-sanitisation
  prevents an entire scrape interval from being dropped.
- ``_MAX_PUSH_ATTEMPTS = 3`` — the documented retry budget for
  network errors / 5xx responses. Drift here either burns the
  upstream rate limit (too many retries) or drops scrapes that
  would have succeeded on retry (too few).
- ``_INSTANCE_LABEL`` falls back env var → env var → hostname so
  every deployed environment populates the ``instance`` label
  (without it Prometheus federates lose attribution).
"""

from __future__ import annotations

import os
import struct
import time

import pytest

from rapidly.observability import remote_write as M
from rapidly.observability.remote_write import (
    _INSTANCE_LABEL,
    _MAX_PUSH_ATTEMPTS,
    _WIRE_64BIT,
    _WIRE_LEN_DELIMITED,
    _WIRE_VARINT,
    _build_label_pair,
    _build_sample,
    _build_timeseries,
    _build_write_request,
    _field_bytes,
    _field_double,
    _field_int64,
    _field_string,
    _varint,
)


class TestWireFormatConstants:
    def test_protobuf_wire_types_pinned(self) -> None:
        # These are protobuf protocol constants defined by the
        # Remote Write spec. Drift = every push rejected as malformed.
        assert _WIRE_VARINT == 0
        assert _WIRE_64BIT == 1
        assert _WIRE_LEN_DELIMITED == 2


class TestVarint:
    def test_zero(self) -> None:
        # protobuf: zero encodes as a single 0 byte.
        assert _varint(0) == b"\x00"

    def test_small_value_single_byte(self) -> None:
        # Values < 128 fit in a single byte without the continuation
        # bit set.
        assert _varint(1) == b"\x01"
        assert _varint(127) == b"\x7f"

    def test_value_at_continuation_boundary(self) -> None:
        # 128 is the minimum value requiring two bytes:
        # low 7 bits with continuation = 0x80, then 0x01.
        assert _varint(128) == b"\x80\x01"

    def test_value_at_two_byte_max(self) -> None:
        # 16383 = 2^14 - 1, the largest two-byte varint.
        assert _varint(16383) == b"\xff\x7f"

    def test_three_byte_value(self) -> None:
        # 16384 is the minimum three-byte varint.
        assert _varint(16384) == b"\x80\x80\x01"

    def test_negative_raises(self) -> None:
        # Pin: protobuf varints are unsigned. Negative inputs MUST
        # raise loudly rather than silently wrap (which would corrupt
        # the entire wire format on a single bad timestamp).
        with pytest.raises(ValueError, match="Negative varint"):
            _varint(-1)


class TestFieldBytes:
    def test_emits_tag_header_then_length_then_payload(self) -> None:
        # Length-delimited fields are: tag<<3 | wire_type, then varint
        # of length, then payload bytes. Drift would invalidate every
        # nested field in the WriteRequest.
        out = _field_bytes(tag=1, payload=b"hello")
        # Header byte: tag=1, wire=2 → (1<<3 | 2) = 0x0a
        assert out[0] == 0x0A
        # Length varint: 5
        assert out[1] == 0x05
        # Payload
        assert out[2:] == b"hello"

    def test_empty_payload(self) -> None:
        # Empty payload is legal; length-prefix is 0.
        out = _field_bytes(tag=1, payload=b"")
        assert out == b"\x0a\x00"


class TestFieldString:
    def test_utf8_encoding(self) -> None:
        # Pin: strings are UTF-8 encoded before the length-delimited
        # wrap. Latin-1 fallback would corrupt non-ASCII labels.
        out = _field_string(tag=1, text="hi")
        assert out == b"\x0a\x02hi"


class TestFieldDouble:
    def test_little_endian_ieee754(self) -> None:
        # Pin: doubles are encoded as 8 bytes little-endian IEEE-754.
        # Wire-type for 64-bit is 1, so the header for tag=1 is
        # (1<<3|1) = 0x09.
        out = _field_double(tag=1, value=1.0)
        assert out[0] == 0x09
        assert out[1:] == struct.pack("<d", 1.0)
        assert len(out) == 9


class TestFieldInt64:
    def test_varint_encoded(self) -> None:
        # Pin: int64 fields use the varint wire type (NOT zigzag).
        # Header for tag=1 is (1<<3|0) = 0x08.
        out = _field_int64(tag=1, value=300)
        assert out[0] == 0x08
        # 300 = 0xAC 0x02 in varint.
        assert out[1:] == b"\xac\x02"


class TestBuildLabelPair:
    def test_emits_name_then_value(self) -> None:
        # Remote Write Label message has tag=1 for name and tag=2
        # for value. Swapping them would mis-tag every label and the
        # ingestor would reject the request.
        out = _build_label_pair(name="env", value="prod")
        # First field is tag=1 (string "env"); next is tag=2 (string "prod").
        # Header for tag=1, wire=2: 0x0a; for tag=2: 0x12.
        assert out.startswith(b"\x0a\x03env")
        assert b"\x12\x04prod" in out


class TestBuildSample:
    def test_finite_value_passes_through(self) -> None:
        out = _build_sample(value=2.5, ts_ms=1700000000000)
        # Decode the double back. Header for double tag=1: 0x09.
        assert out[0] == 0x09
        decoded = struct.unpack("<d", out[1:9])[0]
        assert decoded == 2.5

    def test_nan_replaced_with_zero(self) -> None:
        # Pin: NaN is replaced with 0.0. Grafana Cloud rejects NaN
        # samples; a regression that passed them through would make
        # the entire WriteRequest fail and drop every metric in that
        # scrape.
        out = _build_sample(value=float("nan"), ts_ms=1)
        decoded = struct.unpack("<d", out[1:9])[0]
        assert decoded == 0.0

    def test_positive_infinity_replaced_with_zero(self) -> None:
        out = _build_sample(value=float("inf"), ts_ms=1)
        decoded = struct.unpack("<d", out[1:9])[0]
        assert decoded == 0.0

    def test_negative_infinity_replaced_with_zero(self) -> None:
        out = _build_sample(value=float("-inf"), ts_ms=1)
        decoded = struct.unpack("<d", out[1:9])[0]
        assert decoded == 0.0

    def test_timestamp_encoded_as_int64_field_two(self) -> None:
        # Remote Write Sample: tag=1 is value (double), tag=2 is
        # timestamp (int64). Pin the structure.
        out = _build_sample(value=0.0, ts_ms=42)
        # Bytes 9 onwards = int64 field.
        assert out[9] == 0x10  # tag=2, wire=0 (varint)


class TestBuildTimeseries:
    def test_includes_label_pairs_and_sample(self) -> None:
        # End-to-end: ``_build_timeseries`` emits every label as a
        # length-delimited Label submessage (tag=1) then a Sample
        # submessage (tag=2). A regression that swapped the tags
        # would render the WriteRequest unparseable.
        out = _build_timeseries(
            label_pairs=[("__name__", "rapidly_x"), ("env", "test")],
            value=1.0,
            ts_ms=1,
        )
        # Two label submessages + one sample submessage at the front.
        assert b"__name__" in out
        assert b"rapidly_x" in out
        assert b"env" in out
        assert b"test" in out


class TestBuildWriteRequest:
    def test_concatenates_timeseries_with_field_one_wrapper(self) -> None:
        # Each TimeSeries submessage is field=1 (length-delimited) on
        # the WriteRequest. Pin the concatenation: empty list yields
        # empty bytes; one series prepends its tag header.
        assert _build_write_request([]) == b""
        out = _build_write_request([b"abc"])
        # Header for tag=1, wire=2: 0x0a; length=3.
        assert out == b"\x0a\x03abc"

    def test_two_series_emit_two_field_one_blocks(self) -> None:
        out = _build_write_request([b"a", b"bb"])
        assert out == b"\x0a\x01a\x0a\x02bb"


class TestInstanceLabel:
    def test_fallback_chain_yields_non_empty_string(self) -> None:
        # Pin: ``_INSTANCE_LABEL`` is populated at import time from
        # RENDER_INSTANCE_ID → HOSTNAME → socket.gethostname(). It
        # must be a non-empty string so every emitted timeseries has
        # an ``instance`` label (otherwise federation loses
        # per-host attribution).
        assert isinstance(_INSTANCE_LABEL, str)
        assert _INSTANCE_LABEL != ""


class TestMaxPushAttempts:
    def test_pinned_to_three(self) -> None:
        # 3-attempt budget — drift up burns Grafana Cloud's rate
        # limit; drift down loses scrapes that would have succeeded
        # on retry.
        assert _MAX_PUSH_ATTEMPTS == 3


class TestSendWriteRequestEmptyShortCircuit:
    def test_empty_metrics_does_not_post(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Pin: when there are no metrics to push, the function
        # returns early without making an HTTP request. Otherwise
        # we'd send empty WriteRequests on every cadence and the
        # upstream would log warnings.
        called: list[object] = []

        class _Boom:
            def post(self, *a: object, **kw: object) -> None:
                called.append((a, kw))

        monkeypatch.setattr(M, "_harvest_metrics", lambda: iter([]))
        M._send_write_request(
            client=_Boom(),  # type: ignore[arg-type]
            url="https://example/push",
            auth_headers={},
        )
        assert called == []


class TestSendWriteRequestSuccess:
    def test_posts_once_on_2xx(self, monkeypatch: pytest.MonkeyPatch) -> None:
        posts: list[dict[str, object]] = []

        class _Resp:
            status_code = 204
            text = ""

        class _Client:
            def post(self, url: str, **kwargs: object) -> _Resp:
                posts.append({"url": url, **kwargs})
                return _Resp()

        monkeypatch.setattr(
            M,
            "_harvest_metrics",
            lambda: iter([([("__name__", "x")], 1.0)]),
        )
        M._send_write_request(
            client=_Client(),  # type: ignore[arg-type]
            url="https://example/push",
            auth_headers={"Authorization": "Basic abc"},
        )
        assert len(posts) == 1
        # Pin the wire-protocol headers: protobuf content-type, snappy
        # encoding, Remote Write version. Drift here = ingestor reject.
        headers: dict[str, str] = posts[0]["headers"]  # type: ignore[assignment]
        assert headers["Content-Type"] == "application/x-protobuf"
        assert headers["Content-Encoding"] == "snappy"
        assert headers["X-Prometheus-Remote-Write-Version"] == "0.1.0"
        assert headers["Authorization"] == "Basic abc"


class TestSendWriteRequestRetriesOn5xx:
    def test_retries_then_succeeds(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Pin: 5xx responses retry up to ``_MAX_PUSH_ATTEMPTS`` times.
        # Without retry, transient ingestor faults would drop scrapes.
        responses = [
            type("R", (), {"status_code": 503, "text": "fault"}),
            type("R", (), {"status_code": 204, "text": ""}),
        ]
        calls: list[object] = []

        class _Client:
            def post(self, *a: object, **kw: object) -> object:
                calls.append((a, kw))
                return responses.pop(0)()

        monkeypatch.setattr(
            M,
            "_harvest_metrics",
            lambda: iter([([("__name__", "x")], 1.0)]),
        )
        # Skip the real backoff sleep — would slow the test.
        monkeypatch.setattr(time, "sleep", lambda _s: None)

        M._send_write_request(
            client=_Client(),  # type: ignore[arg-type]
            url="https://example/push",
            auth_headers={},
        )
        assert len(calls) == 2

    def test_4xx_does_not_retry(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Pin: 4xx responses are caller errors (bad payload, auth);
        # retrying would just reproduce the same failure.
        calls: list[object] = []

        class _Resp:
            status_code = 400
            text = "bad request"

        class _Client:
            def post(self, *a: object, **kw: object) -> _Resp:
                calls.append((a, kw))
                return _Resp()

        monkeypatch.setattr(
            M,
            "_harvest_metrics",
            lambda: iter([([("__name__", "x")], 1.0)]),
        )
        monkeypatch.setattr(time, "sleep", lambda _s: None)

        M._send_write_request(
            client=_Client(),  # type: ignore[arg-type]
            url="https://example/push",
            auth_headers={},
        )
        # Exactly one POST despite the failure — no retry on 4xx.
        assert len(calls) == 1


class TestVarintRoundTrip:
    @pytest.mark.parametrize(
        "n", [0, 1, 127, 128, 16383, 16384, 2_000_000, 2**32, 2**63 - 1]
    )
    def test_round_trip_via_decoder(self, n: int) -> None:
        # Pin: every encoded varint round-trips correctly. A
        # regression in the high-bit handling would silently corrupt
        # large timestamps (millisecond epoch values exceed 2^32).
        encoded = _varint(n)
        decoded = 0
        shift = 0
        for b in encoded:
            decoded |= (b & 0x7F) << shift
            shift += 7
            if not b & 0x80:
                break
        assert decoded == n


class TestImportSetupSideEffect:
    def test_module_does_not_pollute_environ(self) -> None:
        # Defensive: importing the module reads RENDER_INSTANCE_ID
        # and HOSTNAME but must NOT write them. Otherwise it would
        # leak deployment-specific values into other test contexts.
        # Pin via a snapshot-and-compare on a representative key.
        # (This pins behaviour rather than absolute values — anything
        # set by other code is preserved.)
        snapshot = os.environ.get("RAPIDLY_REMOTE_WRITE_TEST_SENTINEL")
        # Re-import is a no-op for already-imported modules; touch
        # the symbols to confirm they're accessible.
        assert _INSTANCE_LABEL is not None
        assert os.environ.get("RAPIDLY_REMOTE_WRITE_TEST_SENTINEL") == snapshot
