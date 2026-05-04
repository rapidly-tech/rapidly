"""Tests for ``rapidly/messaging/email/react.py``.

React-based email template rendering. Two load-bearing surfaces:

- ``_transform_avatar_urls_for_email`` rewrites
  ``https://img.logo.dev/...?fallback=404`` to
  ``https://img.logo.dev/...?fallback=monogram``. Email clients
  cache 404 responses aggressively; without the rewrite, every
  email with a missing-domain avatar shows a broken-image icon.
- ``render_email_template`` invokes the React-email subprocess
  with ``[binary, template_name, props_json]`` arg order, and
  raises Exception (NOT returns empty) when the process exits
  non-zero. Drift in arg order would silently render the wrong
  template; drift in error handling would silently send blank
  emails.
"""

from __future__ import annotations

import subprocess
from typing import Any
from unittest.mock import MagicMock

import pytest

from rapidly.messaging.email import react as M
from rapidly.messaging.email.react import (
    _transform_avatar_urls_for_email,
    render_email_template,
)


class TestTransformAvatarUrls:
    def test_logo_dev_404_becomes_monogram(self) -> None:
        # Pin: the documented rewrite. Email clients cache 404
        # responses aggressively; monogram fallback yields a
        # rendered initial letter instead of a broken-image icon.
        before = '"avatar":"https://img.logo.dev/example.com?fallback=404"'
        after = _transform_avatar_urls_for_email(before)
        assert "fallback=monogram" in after
        assert "fallback=404" not in after

    def test_query_args_preserved(self) -> None:
        # Pin: only the ``fallback=`` value changes — every other
        # query parameter (size, format, theme, etc.) is preserved.
        before = '"u":"https://img.logo.dev/x.com?size=128&format=webp&fallback=404&theme=dark"'
        after = _transform_avatar_urls_for_email(before)
        assert "size=128" in after
        assert "format=webp" in after
        assert "theme=dark" in after
        assert "fallback=monogram" in after

    def test_does_not_rewrite_other_domains(self) -> None:
        # Pin: rewrite is scoped to ``img.logo.dev`` host. Drift to
        # a generic ``fallback=404`` regex would mangle unrelated
        # URLs (e.g., user avatars on Gravatar).
        before = '"avatar":"https://example.com/a.png?fallback=404"'
        after = _transform_avatar_urls_for_email(before)
        assert after == before

    def test_does_not_rewrite_already_monogram(self) -> None:
        # Idempotent: running the transform twice is a no-op.
        before = '"u":"https://img.logo.dev/x.com?fallback=monogram"'
        assert _transform_avatar_urls_for_email(before) == before

    def test_handles_empty_input(self) -> None:
        # Defensive: empty string doesn't crash on regex.
        assert _transform_avatar_urls_for_email("") == ""


class TestRenderEmailTemplate:
    def _email(
        self, *, template: str = "welcome", props_dict: dict[str, Any] | None = None
    ) -> Any:
        # Build a stub Email that quacks like the real Pydantic
        # ``Email`` (only ``template`` + ``props.model_dump_json()``
        # are read by the renderer).
        email = MagicMock()
        email.template = template
        email.props = MagicMock()
        email.props.model_dump_json = MagicMock(
            return_value="" if props_dict is None else "{}"
        )
        return email

    def test_invokes_subprocess_with_binary_template_props(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: arg order is [binary, template_name, props_json].
        # Drift would silently render the wrong template (since
        # both template name and props are strings, no schema
        # mismatch would surface).
        captured: dict[str, Any] = {}

        class _FakeProc:
            returncode = 0

            def communicate(self) -> tuple[bytes, bytes]:
                return (b"<html>rendered</html>", b"")

        def fake_popen(args: list[str], **kwargs: Any) -> _FakeProc:
            captured["args"] = args
            captured["kwargs"] = kwargs
            return _FakeProc()

        monkeypatch.setattr(subprocess, "Popen", fake_popen)
        from rapidly.config import settings as settings_obj

        monkeypatch.setattr(
            settings_obj, "EMAIL_RENDERER_BINARY_PATH", "/usr/bin/email-render"
        )

        email = self._email(template="welcome")
        email.props.model_dump_json.return_value = '{"name":"Alice"}'

        result = render_email_template(email)
        assert result == "<html>rendered</html>"
        assert captured["args"] == [
            "/usr/bin/email-render",
            "welcome",
            '{"name":"Alice"}',
        ]
        # Pin: stdout + stderr captured (not inherited) so the
        # binary's debug output doesn't pollute the API server's
        # log stream.
        assert captured["kwargs"]["stdout"] == subprocess.PIPE
        assert captured["kwargs"]["stderr"] == subprocess.PIPE

    def test_applies_avatar_url_transform_before_subprocess(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin: the rewrite happens BEFORE the props_json is passed
        # to the subprocess. A regression that did the rewrite on
        # the rendered HTML would miss the case where the React
        # template inlines the URL into a non-rewritable context
        # (e.g., a CSS background-image).
        captured: dict[str, Any] = {}

        class _FakeProc:
            returncode = 0

            def communicate(self) -> tuple[bytes, bytes]:
                return (b"", b"")

        def fake_popen(args: list[str], **kwargs: Any) -> _FakeProc:
            captured["args"] = args
            return _FakeProc()

        monkeypatch.setattr(subprocess, "Popen", fake_popen)
        from rapidly.config import settings as settings_obj

        monkeypatch.setattr(settings_obj, "EMAIL_RENDERER_BINARY_PATH", "/x")

        email = self._email()
        email.props.model_dump_json.return_value = (
            '{"avatar":"https://img.logo.dev/y.com?fallback=404"}'
        )
        render_email_template(email)
        # The third arg (props_json) must have been transformed.
        assert "fallback=monogram" in captured["args"][2]
        assert "fallback=404" not in captured["args"][2]

    def test_non_zero_exit_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Pin: subprocess failure → raise (NOT silently return
        # empty). A regression to "return stdout regardless"
        # would silently send blank emails when the renderer
        # crashed.
        class _FailProc:
            returncode = 1

            def communicate(self) -> tuple[bytes, bytes]:
                return (b"", b"renderer crashed: missing template")

        monkeypatch.setattr(subprocess, "Popen", lambda *a, **kw: _FailProc())
        from rapidly.config import settings as settings_obj

        monkeypatch.setattr(settings_obj, "EMAIL_RENDERER_BINARY_PATH", "/x")

        with pytest.raises(Exception, match="renderer crashed"):
            render_email_template(self._email())

    def test_decodes_stdout_as_utf8(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Pin: stdout decoded as UTF-8 — emails commonly carry
        # non-ASCII content (curly quotes, accented names). Drift
        # to ASCII would crash on every i18n send.
        class _Proc:
            returncode = 0

            def communicate(self) -> tuple[bytes, bytes]:
                return ("héllo ✨".encode(), b"")

        monkeypatch.setattr(subprocess, "Popen", lambda *a, **kw: _Proc())
        from rapidly.config import settings as settings_obj

        monkeypatch.setattr(settings_obj, "EMAIL_RENDERER_BINARY_PATH", "/x")

        result = render_email_template(self._email())
        assert result == "héllo ✨"


class TestExports:
    def test_render_email_template_exported(self) -> None:
        # Pin the public API of the module.
        assert "render_email_template" in M.__all__
