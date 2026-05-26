"""Tests for the code-sandbox node handler.

These cover the **structure** layer: subprocess + rlimit + tempdir
+ JSON I/O. The seccomp filter ships in M4.5b after external
review; its tests live alongside that PR.

Tests run on Linux only — the ``resource`` module + setrlimit
behaviour is unix-specific. Skipping on macOS / Windows isn't
strictly necessary for CI (Linux) but the marker keeps local
dev clean.
"""

from __future__ import annotations

import platform

import pytest

from rapidly.agents.execution.handlers.code import CodeNodeError, code_handler

pytestmark = pytest.mark.skipif(
    platform.system() != "Linux",
    reason="code-sandbox handler relies on Linux setrlimit semantics",
)


def _enable_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    """Flip the feature flag on for the duration of a test.

    Direct attribute patching on the cached settings instance —
    the config layer reads via ``getattr(settings, ...)`` which
    monkeypatch handles cleanly.
    """
    from rapidly.config import settings

    monkeypatch.setattr(settings, "AGENTS_CODE_SANDBOX_ENABLED", True, raising=False)


@pytest.mark.asyncio
class TestFeatureFlagGate:
    async def test_refuses_when_flag_off(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Default config has the flag off — the handler should
        # refuse before doing anything dangerous.
        from rapidly.config import settings

        monkeypatch.setattr(
            settings, "AGENTS_CODE_SANDBOX_ENABLED", False, raising=False
        )
        with pytest.raises(CodeNodeError, match="gated behind"):
            await code_handler({}, {"source": "def handler(x): return {}"}, {})


@pytest.mark.asyncio
class TestValidation:
    async def test_requires_source(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _enable_flag(monkeypatch)
        with pytest.raises(CodeNodeError, match="source is required"):
            await code_handler({}, {}, {})

    async def test_rejects_empty_source(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _enable_flag(monkeypatch)
        with pytest.raises(CodeNodeError, match="source is required"):
            await code_handler({}, {"source": "   "}, {})


@pytest.mark.asyncio
class TestHappyPath:
    async def test_doubles_input(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _enable_flag(monkeypatch)
        out = await code_handler(
            {},
            {"source": "def handler(x): return {'doubled': x['n'] * 2}"},
            {"n": 21},
        )
        assert out["result"] == {"doubled": 42}

    async def test_captures_stdout(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _enable_flag(monkeypatch)
        out = await code_handler(
            {},
            {
                "source": (
                    "def handler(x):\n"
                    "    print('hello from sandbox')\n"
                    "    return {'ok': True}\n"
                )
            },
            {},
        )
        assert out["result"] == {"ok": True}
        assert "hello from sandbox" in out["stdout"]


@pytest.mark.asyncio
class TestFailureModes:
    async def test_missing_handler_function_fails_loudly(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _enable_flag(monkeypatch)
        with pytest.raises(CodeNodeError, match="exited with"):
            await code_handler(
                {},
                # No ``handler`` defined.
                {"source": "x = 42\n"},
                {},
            )

    async def test_non_dict_return_fails_loudly(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _enable_flag(monkeypatch)
        with pytest.raises(CodeNodeError, match="exited with"):
            await code_handler(
                {},
                {"source": "def handler(x): return [1, 2, 3]"},
                {},
            )

    async def test_user_exception_surfaces(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _enable_flag(monkeypatch)
        with pytest.raises(CodeNodeError, match="exited with"):
            await code_handler(
                {},
                {"source": "def handler(x): raise ValueError('boom')"},
                {},
            )


@pytest.mark.asyncio
class TestResourceLimits:
    # NOTE: fork prevention via NPROC is environment-dependent
    # (whether echo is a shell builtin, whether the rlimit applies
    # cleanly when set below the current uid's process count).
    # The real fork/exec block lives in the M4.5b seccomp filter
    # which denies the ``clone`` / ``fork`` / ``execve`` syscalls
    # directly. Tests for that path live with that PR.

    async def test_memory_bomb_caught(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # RLIMIT_AS=512MB; allocating 1GB should fail.
        _enable_flag(monkeypatch)
        with pytest.raises(CodeNodeError):
            await code_handler(
                {},
                {
                    "source": (
                        "def handler(x):\n"
                        "    big = bytearray(1024 * 1024 * 1024)\n"
                        "    return {}\n"
                    )
                },
                {},
            )
