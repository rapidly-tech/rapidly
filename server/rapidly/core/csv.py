"""Streaming CSV writer for async HTTP responses.

``IterableCSVWriter`` produces CSV rows lazily so that large exports
can be streamed via ``StreamingResponse`` without buffering the entire
result set in memory.
"""

from __future__ import annotations

import collections
import csv
from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import _csv

from .email import EmailNotValidError, validate_email

# ── Parsing Helpers ──


def extract_emails_from_csv(lines: Iterable[str]) -> set[str]:
    """Parse a CSV and return validated email addresses from the first email-like column."""
    reader = csv.DictReader(lines)
    if reader.fieldnames is None:
        return set()

    email_col = next((f for f in reader.fieldnames if "email" in f.lower()), None)
    if email_col is None:
        return set()

    result: set[str] = set()
    for row in reader:
        addr = row.get(email_col)
        if addr is None:
            continue
        try:
            validate_email(addr)
        except EmailNotValidError:
            continue
        result.add(addr)
    return result


get_emails_from_csv = extract_emails_from_csv


# ── CSV Writer ──


class IterableCSVWriter:
    """Wraps :mod:`csv.writer` so each row is returned as a string.

    Useful for streaming CSV responses via ``StreamingResponse``.
    """

    writer: _csv._writer

    def __init__(
        self,
        dialect: _csv._DialectLike = "excel",
        *,
        delimiter: str = ",",
        quotechar: str | None = '"',
        escapechar: str | None = None,
        doublequote: bool = True,
        skipinitialspace: bool = False,
        lineterminator: str = "\r\n",
        quoting: _csv._QuotingType = 0,
        strict: bool = False,
    ) -> None:
        self._buffer: collections.deque[str] = collections.deque()
        self.writer = csv.writer(
            self,
            dialect=dialect,
            delimiter=delimiter,
            quotechar=quotechar,
            escapechar=escapechar,
            doublequote=doublequote,
            skipinitialspace=skipinitialspace,
            lineterminator=lineterminator,
            quoting=quoting,
            strict=strict,
        )

    def getrow(self, row: Iterable[Any]) -> str:
        self.writer.writerow(row)
        return self.read()

    def write(self, line: str) -> None:
        self._buffer.append(line)

    def read(self) -> str:
        return self._buffer.popleft()
