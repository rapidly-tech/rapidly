#!/usr/bin/env python3
"""
email_login_code_notifier.py - Rapidly Login Code Desktop Notifier
Version: 1.0.0-rapidly

This script is intended to take in the stdin/stderr from the Dramatiq worker
like so:

    uv run task worker 2>&1 | uv run python ../dev/email_login_code_notifier.py

When the script encounters what looks like a login code, it will show
a desktop notification with the code and copy the code to the clipboard.

Currently only supports macOS (uses osascript for notifications).
"""
import platform
import re
import sys
import subprocess

# Pattern to match login codes in email output
LOGIN_CODE_PATTERN = re.compile(r">([0-9A-Z]{6})</p>")
NOTIFICATION_TITLE = "Rapidly login email"


def main() -> None:
    # Only works on macOS
    assert platform.system() == "Darwin", (
        "This notifier requires macOS (osascript)"
    )

    for line in sys.stdin:
        matches = LOGIN_CODE_PATTERN.findall(line)

        for match in matches:
            subprocess.run(
                [
                    "osascript",
                    "-e",
                    f'display notification "Found login code {match}. Copied to clipboard" with title "{NOTIFICATION_TITLE}" sound name "default"',
                    "-e",
                    f'set the clipboard to "{match}"',
                ]
            )

        # Also print the line to stdout to maintain stream flow
        print(line, end="", flush=True)


if __name__ == "__main__":
    main()
