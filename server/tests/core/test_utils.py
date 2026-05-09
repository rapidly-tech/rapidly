"""Tests for ``rapidly/core/utils.py`` — timezone-aware now_utc, UUIDv4
generator, and human-readable byte-size formatter."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from rapidly.core.utils import create_uuid, human_readable_size, now_utc


class TestNowUtc:
    def test_returns_a_timezone_aware_datetime(self) -> None:
        dt = now_utc()
        # The whole point of ``now_utc`` vs ``datetime.utcnow`` is
        # returning an AWARE datetime (utcnow() returns naïve).
        assert dt.tzinfo is not None
        assert dt.utcoffset() is not None

    def test_is_in_UTC_tz(self) -> None:
        dt = now_utc()
        assert dt.tzinfo == UTC

    def test_is_comparable_with_timezone_aware_datetimes(self) -> None:
        # Naïve vs aware comparison raises TypeError in Python, so this
        # smoke-tests "we actually get aware" by comparing to another
        # aware datetime without exceptions.
        reference = datetime(2020, 1, 1, tzinfo=UTC)
        assert now_utc() > reference


class TestCreateUuid:
    def test_returns_a_uuid_instance(self) -> None:
        value = create_uuid()
        assert isinstance(value, uuid.UUID)

    def test_is_version_4(self) -> None:
        assert create_uuid().version == 4

    def test_produces_distinct_values_across_calls(self) -> None:
        values = {create_uuid() for _ in range(20)}
        assert len(values) == 20


class TestHumanReadableSize:
    def test_formats_bytes_under_1KB_as_B(self) -> None:
        assert human_readable_size(0) == "0.0 B"
        assert human_readable_size(1) == "1.0 B"
        assert human_readable_size(1023) == "1023.0 B"

    def test_transitions_to_KB_at_1024(self) -> None:
        assert human_readable_size(1024) == "1.0 KB"
        assert human_readable_size(1536) == "1.5 KB"

    def test_formats_megabyte_range(self) -> None:
        assert human_readable_size(1024 * 1024) == "1.0 MB"
        assert human_readable_size(int(1024 * 1024 * 2.5)) == "2.5 MB"

    def test_formats_gigabyte_range(self) -> None:
        one_gb = 1024**3
        assert human_readable_size(one_gb) == "1.0 GB"

    def test_handles_terabyte_plus(self) -> None:
        one_tb = 1024**4
        assert human_readable_size(one_tb) == "1.0 TB"
        one_pb = 1024**5
        assert human_readable_size(one_pb) == "1.0 PB"

    def test_clamps_at_Y_for_astronomically_huge_values(self) -> None:
        # The prefix table ends at Z, so anything beyond falls through
        # to the final "Y" (yottabyte) branch. Pin this so the
        # "ran out of prefixes" fallback isn't accidentally removed.
        huge = 1024**9  # much bigger than YB
        out = human_readable_size(huge)
        assert "Y" in out
        assert out.endswith("B")

    def test_honours_custom_suffix(self) -> None:
        # ``human_readable_size`` is generic over unit — callers can pass
        # "bps" for bandwidth, for example. Pinned so refactors keep the
        # suffix arg.
        assert human_readable_size(2048, suffix="bps") == "2.0 Kbps"

    def test_handles_negative_values(self) -> None:
        # Uses abs() in the comparison, so negative sizes still format.
        out = human_readable_size(-2048)
        assert out.startswith("-2.0")
        assert "KB" in out
