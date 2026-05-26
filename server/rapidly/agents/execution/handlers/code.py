"""Code node handler — runs user-supplied Python in a sandbox.

Security posture (per ``M4_EXECUTION.md`` §4.5):

This handler is the ONLY untrusted-input → executable surface in
the agent runtime. The workflow author is workspace-internal but
still untrusted relative to the API process; a bug here can be
RCE.

Defence layers (this PR ships **structure** + rlimit; seccomp
syscall filter lands in M4.5b after external review):

1. Subprocess isolation (separate address space; OOM kills the
   child, not the worker; gVisor reserved for M9 if real isolation
   matters).
2. ``resource.setrlimit`` (preexec_fn): bounds memory + CPU +
   open-file count + process count. Even without seccomp, a
   misbehaving script can't fork-bomb or memory-bomb the worker.
3. Tempdir scoping: each call gets its own ``mkdtemp`` and writes
   only there. Cleanup is unconditional via try/finally.
4. JSON-only I/O: input + output exchanged through files. No
   stdin pipes, no shell, no env-inheritance beyond what we set.
5. Feature flag (``AGENTS_CODE_SANDBOX_ENABLED``) default OFF.
   The seccomp filter (M4.5b) is what lets us flip this on; until
   then the node refuses to run.

Out of scope here (M4.5b):
- libseccomp filter that denies syscalls outside the allowlist
- audit + sign-off review of the filter contents
- the apt install of libseccomp-dev in the worker Dockerfile

What can still bite even with rlimit:
- File reads inside the worker's process scope (e.g.
  /proc/self/environ). The seccomp filter blocks these by
  denying ``open`` outside the tempdir.
- Network sockets. The seccomp filter blocks ``socket``.
- ``exec``-ing other binaries. The filter denies ``execve``.

Hence the feature flag — DO NOT enable this in production until
M4.5b lands AND the filter has been reviewed.
"""

from __future__ import annotations

import asyncio
import json
import resource
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from rapidly.config import settings


class CodeNodeError(RuntimeError):
    """Surfaces to the engine's per-node failure path."""


# Per-process resource caps applied via ``preexec_fn``. Values
# chosen conservatively for v1; the workflow author can't override
# them from node_config (deliberately — these are the worker's
# protection, not the workflow's tuning knob).
_RLIMIT_AS = 512 * 1024 * 1024  # 512 MiB address space
_RLIMIT_CPU = 30  # seconds of CPU time
_RLIMIT_NOFILE = 32  # open file descriptors
_RLIMIT_NPROC = 1  # no forking — the script can't fork-bomb


# Subprocess wall-clock timeout. CPU-rlimit handles compute-bound
# loops; this catches sleep / IO-wait loops.
_WALL_TIMEOUT_S = 60.0


# Maximum bytes the script's stdout is allowed to produce. Stdout
# is captured for diagnostic only — output.json is the structured
# return channel.
_MAX_STDOUT_BYTES = 100 * 1024


_RUNNER_TEMPLATE = """\
# Sandboxed runner — reads input.json, executes the user's handler,
# writes output.json. Anything the user code prints to stdout/err
# is captured but not the return channel.
import json
import sys
from pathlib import Path

workdir = Path(__file__).resolve().parent

with (workdir / 'input.json').open() as fh:
    input_data = json.load(fh)

# Load the user's module without imports leaking into the runner's
# namespace. ``exec`` against an explicit namespace dict makes the
# handler discoverable.
ns = {'__name__': 'user_code'}
with (workdir / 'user_code.py').open() as fh:
    exec(fh.read(), ns)

handler = ns.get('handler')
if not callable(handler):
    print('user_code.py must define ``def handler(input):``', file=sys.stderr)
    sys.exit(2)

result = handler(input_data)
if result is None:
    result = {}
elif not isinstance(result, dict):
    print(f'handler must return dict or None, got {type(result).__name__}', file=sys.stderr)
    sys.exit(3)

with (workdir / 'output.json').open('w') as fh:
    json.dump(result, fh)
"""


def _apply_rlimits() -> None:
    """preexec_fn that pins the child's resource ceilings.

    Runs in the child after fork, before exec. Anything that
    raises here kills the child silently — keep it simple and
    fail-loud at the Python level on the parent side.
    """
    resource.setrlimit(resource.RLIMIT_AS, (_RLIMIT_AS, _RLIMIT_AS))
    resource.setrlimit(resource.RLIMIT_CPU, (_RLIMIT_CPU, _RLIMIT_CPU))
    resource.setrlimit(resource.RLIMIT_NOFILE, (_RLIMIT_NOFILE, _RLIMIT_NOFILE))
    resource.setrlimit(resource.RLIMIT_NPROC, (_RLIMIT_NPROC, _RLIMIT_NPROC))


async def code_handler(
    ctx: dict[str, Any],
    node_config: dict[str, Any],
    input_data: dict[str, Any],
) -> dict[str, Any]:
    """Execute a user-supplied Python ``handler(input) -> dict``.

    ``node_config`` fields:
        source: str    Python source defining ``def handler(input):``
    """
    if not getattr(settings, "AGENTS_CODE_SANDBOX_ENABLED", False):
        raise CodeNodeError(
            "code node is gated behind AGENTS_CODE_SANDBOX_ENABLED — "
            "the seccomp filter (M4.5b) lands first; flip the flag "
            "only after the filter has been reviewed"
        )

    source = node_config.get("source")
    if not isinstance(source, str) or not source.strip():
        raise CodeNodeError("source is required")

    workdir = Path(tempfile.mkdtemp(prefix="rapidly-code-"))
    try:
        (workdir / "user_code.py").write_text(source)
        (workdir / "input.json").write_text(json.dumps(input_data))
        (workdir / "runner.py").write_text(_RUNNER_TEMPLATE)

        # Subprocess. ``env={}`` strips inherited env — the script
        # gets only what we hand it. ``cwd=workdir`` plus the
        # runner's path-relative reads keeps file IO scoped.
        proc = await asyncio.to_thread(
            subprocess.run,
            [sys.executable, str(workdir / "runner.py")],
            cwd=str(workdir),
            env={},
            capture_output=True,
            timeout=_WALL_TIMEOUT_S,
            preexec_fn=_apply_rlimits,
            check=False,
        )

        stdout = proc.stdout[:_MAX_STDOUT_BYTES] if proc.stdout else b""
        stderr = proc.stderr[:_MAX_STDOUT_BYTES] if proc.stderr else b""

        if proc.returncode != 0:
            raise CodeNodeError(
                f"runner exited with {proc.returncode}: {stderr.decode('utf-8', errors='replace')[:500]}"
            )

        out_path = workdir / "output.json"
        if not out_path.exists():
            raise CodeNodeError("runner produced no output.json")
        try:
            result = json.loads(out_path.read_text())
        except ValueError as exc:
            raise CodeNodeError(f"output.json is not valid JSON: {exc}") from exc
        if not isinstance(result, dict):
            raise CodeNodeError(
                f"output.json must be a dict, got {type(result).__name__}"
            )

        return {
            "result": result,
            "stdout": stdout.decode("utf-8", errors="replace"),
            "stderr": stderr.decode("utf-8", errors="replace"),
        }
    except subprocess.TimeoutExpired as exc:
        raise CodeNodeError(
            f"runner exceeded wall-clock timeout of {_WALL_TIMEOUT_S}s"
        ) from exc
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
