"""Extended tests for ``rapidly/core/csv.py``.

The existing ``test_csv.py`` covers ``get_emails_from_csv`` happy
paths. This file pins the uncovered surfaces:

- ``IterableCSVWriter`` streams per-row CSV strings — used by the
  admin export endpoints to avoid buffering 100 k-row exports in
  memory
- ``extract_emails_from_csv`` edge cases (empty input, no header)
- ``get_emails_from_csv`` alias remains a function reference to
  ``extract_emails_from_csv`` (backward compat)
"""

from __future__ import annotations

from rapidly.core.csv import (
    IterableCSVWriter,
    extract_emails_from_csv,
    get_emails_from_csv,
)


class TestIterableCSVWriter:
    def test_produces_a_single_row_string(self) -> None:
        writer = IterableCSVWriter()
        row = writer.getrow(["alice", "alice@test.com"])
        assert row == "alice,alice@test.com\r\n"

    def test_quotes_values_with_commas(self) -> None:
        # Default excel dialect double-quotes fields containing the
        # delimiter. Pinning prevents a regression to ``quoting=NONE``
        # that would break CSV parsing on the consumer side.
        writer = IterableCSVWriter()
        row = writer.getrow(["Doe, John", "j@test.com"])
        assert '"Doe, John"' in row

    def test_default_line_terminator_is_crlf(self) -> None:
        # ``\r\n`` is the RFC 4180 CSV line terminator; a regression
        # to ``\n`` would surface as mangled rows on Excel imports.
        writer = IterableCSVWriter()
        assert writer.getrow(["a"]).endswith("\r\n")

    def test_custom_delimiter(self) -> None:
        writer = IterableCSVWriter(delimiter=";")
        assert writer.getrow(["a", "b"]) == "a;b\r\n"

    def test_multiple_rows_stream_independently(self) -> None:
        # Each getrow call returns only its own row — no buffering
        # carry-over, which is the streaming contract that lets
        # StreamingResponse yield chunks as it reads.
        writer = IterableCSVWriter()
        r1 = writer.getrow(["a", "b"])
        r2 = writer.getrow(["c", "d"])
        assert r1 == "a,b\r\n"
        assert r2 == "c,d\r\n"

    def test_buffer_is_drained_after_read(self) -> None:
        # ``read()`` pops from the internal deque — a regression
        # that left entries in the buffer would leak memory across
        # long-running exports.
        writer = IterableCSVWriter()
        writer.getrow(["a"])
        assert len(writer._buffer) == 0

    def test_numeric_values_are_stringified(self) -> None:
        writer = IterableCSVWriter()
        row = writer.getrow([42, 3.14, True])
        assert "42" in row
        assert "3.14" in row
        assert "True" in row


class TestExtractEmailsEdgeCases:
    def test_no_header_returns_empty_set(self) -> None:
        # csv.DictReader uses the first line as fieldnames; an
        # empty iterable has no header row.
        assert extract_emails_from_csv([]) == set()

    def test_deduplicates_repeated_addresses(self) -> None:
        # DictReader yields every row; ``set`` deduplicates. Pin
        # the behaviour so a refactor to list-return doesn't
        # accidentally surface duplicates (import flows expect
        # deduped inputs).
        result = extract_emails_from_csv(
            [
                "email",
                "alice@test.com",
                "alice@test.com",
                "bob@test.com",
            ]
        )
        assert result == {"alice@test.com", "bob@test.com"}

    def test_picks_first_email_like_column(self) -> None:
        # If a row has multiple email-ish columns, the first one
        # wins — prevents "personal_email" from beating "email"
        # on a schema that puts personal first.
        result = extract_emails_from_csv(
            [
                "email,personal_email",
                "work@test.com,personal@test.com",
            ]
        )
        assert result == {"work@test.com"}


class TestGetEmailsAlias:
    def test_is_reference_to_extract_emails(self) -> None:
        # ``get_emails_from_csv = extract_emails_from_csv`` is a
        # backward-compat alias. Pinning the reference identity
        # prevents a regression that replaces the alias with a
        # differently-behaving shim.
        assert get_emails_from_csv is extract_emails_from_csv
