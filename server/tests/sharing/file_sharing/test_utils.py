"""Tests for ``rapidly/sharing/file_sharing/utils.py::hash_ip``.

The helper backs rate-limit keys; it must be deterministic (same IP ⇒
same hash), HMAC-keyed (different app secret ⇒ different hash), and
preserve privacy (raw IP is never recoverable from the output).
"""

from __future__ import annotations

from rapidly.sharing.file_sharing.utils import hash_ip


class TestHashIp:
    def test_is_deterministic_for_the_same_input(self) -> None:
        # Deterministic across calls — the rate-limit keyspace relies on
        # this to actually throttle repeat offenders.
        a = hash_ip("1.2.3.4")
        b = hash_ip("1.2.3.4")
        assert a == b

    def test_different_ips_produce_different_hashes(self) -> None:
        assert hash_ip("1.2.3.4") != hash_ip("5.6.7.8")

    def test_hash_is_16_lowercase_hex_chars(self) -> None:
        digest = hash_ip("203.0.113.42")
        # 16 chars = 64 bits, which is the truncated HMAC output size
        # the module documents.
        assert len(digest) == 16
        assert digest == digest.lower()
        int(digest, 16)  # must be parseable as hex

    def test_raw_ip_is_not_a_substring_of_the_hash(self) -> None:
        ip = "8.8.8.8"
        digest = hash_ip(ip)
        assert ip not in digest

    def test_ipv6_inputs_hash_without_error(self) -> None:
        # hash_ip is typed str → str; IPv6 literals shouldn't crash.
        digest = hash_ip("2001:4860:4860::8888")
        assert len(digest) == 16
