#!/usr/bin/env python3
"""Notification hook: forward "the session needs you" events to Telegram.

Registered with a matcher for idle / needs-input notifications only; permission
prompts are handled by hook_permission.py, which can actually answer them.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import afk_common as afk  # noqa: E402


def main():
    raw = sys.stdin.read()
    try:
        event = json.loads(raw) if raw.strip() else {}
    except ValueError:
        event = {}

    state = afk.active_state(event.get("session_id") or "")
    if state is None:
        return 0

    config = afk.load_config()
    if not config:
        return 0

    message = (event.get("message") or "").strip() or afk.t("notify.default")
    project = os.path.basename(event.get("cwd") or "") or "claude"
    afk.send(
        config["bot_token"],
        config["chat_id"],
        afk.t("notify.line", project=project, message=message),
    )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception as exc:
        afk.log("notify hook crashed: %r" % (exc,))
        sys.exit(0)
