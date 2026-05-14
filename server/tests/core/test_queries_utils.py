"""Tests for ``rapidly/core/queries/utils.py``: ``escape_like`` and ``ilike_substring``.

``escape_like`` is the gate between user-supplied search terms and
``ILIKE``/``LIKE`` expressions. Without it, a search for ``%`` matches
every row; a search for ``_`` matches any single character. Worse —
a search for ``\\%`` would match ``%`` literally in an already-escaped
string without the fix.

The ordering of replacements is security-critical: the backslash MUST
be escaped first so the subsequent ``%`` / ``_`` replacements don't
produce a double-escape that inserts an unintended literal backslash.
"""

from __future__ import annotations

import pytest

from rapidly.core.queries.utils import escape_like, ilike_substring


class TestEscapeLike:
    def test_plain_string_passes_through_unchanged(self) -> None:
        assert escape_like("hello world") == "hello world"
        assert escape_like("") == ""

    def test_percent_is_escaped(self) -> None:
        # ``%`` = "any sequence of characters" in SQL LIKE.
        assert escape_like("50%") == "50\\%"
        assert escape_like("%foo%") == "\\%foo\\%"

    def test_underscore_is_escaped(self) -> None:
        # ``_`` = "any single character".
        assert escape_like("a_b") == "a\\_b"

    def test_backslash_is_escaped_first(self) -> None:
        # The backslash MUST be escaped before ``%``/``_``. Otherwise
        # escaping ``%`` first would produce ``\%``, and the subsequent
        # backslash-escape pass would turn it into ``\\%`` which is
        # "literal backslash + any sequence" — widening the match, not
        # narrowing it.
        assert escape_like("\\") == "\\\\"

    def test_combined_metacharacters(self) -> None:
        # Pattern "50%" followed by "a_b" with a literal backslash.
        assert escape_like("50%a_b\\") == "50\\%a\\_b\\\\"

    def test_ordering_is_correct_backslash_then_percent(self) -> None:
        # Input "\%" should round-trip to "\\\\\\%" (literal backslash
        # + literal percent). If ``%`` were escaped first we'd get
        # "\\%" → wait, let me re-derive: initially "\%". First
        # replacement: "\" → "\\" gives "\\%". Second replacement:
        # "%" → "\%" gives "\\\%" (escaped backslash + escaped percent).
        # This is the correct order — a literal backslash + literal
        # percent in the original becomes a literal backslash + escaped
        # percent in the output.
        assert escape_like("\\%") == "\\\\\\%"

    def test_multiple_consecutive_metacharacters(self) -> None:
        assert escape_like("%%") == "\\%\\%"
        assert escape_like("__") == "\\_\\_"
        assert escape_like("\\\\") == "\\\\\\\\"

    def test_no_false_positives_for_hash_or_asterisk(self) -> None:
        # ``#``, ``*``, ``?`` are NOT SQL LIKE metacharacters — they
        # must pass through unchanged.
        assert escape_like("#*?") == "#*?"

    def test_returns_a_string(self) -> None:
        # Explicit type-shape pin — callers may pass the result to
        # ``bindparam`` which expects str.
        assert isinstance(escape_like("x"), str)

    def test_unicode_passes_through(self) -> None:
        # Non-ASCII inputs aren't metacharacters — preserved.
        assert escape_like("café") == "café"
        assert escape_like("🔒") == "🔒"


class TestIlikeSubstring:
    """``ilike_substring`` is the safe wrapper: callers can't forget the
    ``escape="\\"`` clause because the helper passes it for them.  Tests
    here pin the SQL shape and the wildcard-escape behaviour by
    compiling the returned clause to literal SQL.
    """

    @staticmethod
    def _compile(clause: object) -> str:
        return str(
            clause.compile(compile_kwargs={"literal_binds": True})  # type: ignore[attr-defined]
        )

    def test_substring_anchor_emits_double_percent_pattern(self) -> None:
        from sqlalchemy import select

        from rapidly.models import Workspace

        clause = ilike_substring(Workspace.name, "acme")
        sql = self._compile(clause).lower()
        # ILIKE compiles as LOWER(col) LIKE LOWER(...) in the default
        # dialect.  Pin the substring shape and the ESCAPE clause.
        assert "lower(workspaces.name) like" in sql
        assert "%acme%" in sql
        assert " escape " in sql

        # And the wider query — embed in a select to confirm the
        # clause composes correctly.
        stmt = select(Workspace).where(clause)
        stmt_sql = self._compile(stmt).lower()
        assert " escape " in stmt_sql

    def test_prefix_anchor_emits_trailing_percent_only(self) -> None:
        from rapidly.models import Workspace

        clause = ilike_substring(Workspace.slug, "foo", anchor="prefix")
        sql = self._compile(clause).lower()
        # No leading % — match begins-with.
        assert "%foo%" not in sql
        assert "'foo%'" in sql
        assert " escape " in sql

    def test_suffix_anchor_emits_leading_percent_only(self) -> None:
        from rapidly.models import Workspace

        clause = ilike_substring(Workspace.slug, "bar", anchor="suffix")
        sql = self._compile(clause).lower()
        assert "'%bar'" in sql
        assert "'%bar%'" not in sql

    def test_unknown_anchor_raises(self) -> None:
        from rapidly.models import Workspace

        with pytest.raises(ValueError, match="unknown anchor"):
            ilike_substring(Workspace.name, "x", anchor="middle")  # type: ignore[arg-type]

    def test_wildcards_in_user_input_get_escaped(self) -> None:
        from rapidly.models import Workspace

        clause = ilike_substring(Workspace.name, "50%_off")
        sql = self._compile(clause).lower()
        # ``%`` and ``_`` from user input become backslash-escaped so
        # Postgres LIKE treats them as literals; the ESCAPE clause is
        # what makes the escapes take effect.
        assert "50\\%\\_off" in sql
        assert " escape " in sql

    def test_composes_with_func_lower(self) -> None:
        from sqlalchemy import func

        from rapidly.models import Workspace

        clause = ilike_substring(func.lower(Workspace.email), "test@example.com")
        sql = self._compile(clause).lower()
        # ``func.lower(col)`` composes with ``ilike`` cleanly.
        assert "lower(workspaces.email)" in sql
        assert " escape " in sql
