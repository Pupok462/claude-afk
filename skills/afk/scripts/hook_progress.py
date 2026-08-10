#!/usr/bin/env python3
"""PostToolUse hook: keep one live "working…" message updated in Telegram.

Without this the phone sees nothing between the acknowledgement and the
finished answer, and a long turn looks like the session died. This edits a
single message in place instead of spamming the chat; hook_stop.py deletes it
when the real answer arrives.
"""

import json
import os
import sys
import time

# Cheapest possible no-op when AFK is off: this runs after *every* tool call.
_AFK_DIR = os.environ.get("AFK_HOME") or os.path.join(
    os.path.expanduser("~"), ".claude", "afk"
)
if not os.path.exists(os.path.join(_AFK_DIR, "active.json")):
    sys.exit(0)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import afk_common as afk  # noqa: E402

THROTTLE_SECONDS = 4  # Telegram dislikes rapid edits of the same message


def main():
    raw = sys.stdin.read()
    try:
        event = json.loads(raw) if raw.strip() else {}
    except ValueError:
        event = {}

    state = afk.active_state(event.get("session_id") or "")
    if state is None:
        return 0

    message_id = state.get("status_message_id")
    if not message_id:
        return 0  # nothing in flight — the turn was not started from Telegram

    config = afk.load_config()
    if not config:
        return 0

    now = time.time()
    steps = int(state.get("progress_steps", 0)) + 1
    state["progress_steps"] = steps

    last = float(state.get("last_progress_at", 0) or 0)
    if last and now - last < THROTTLE_SECONDS:
        afk.persist(state)  # keep the counter honest, skip the network call
        return 0
    state["last_progress_at"] = now

    tool_name = event.get("tool_name") or "?"
    detail = afk.describe_tool(tool_name, event.get("tool_input"), limit=120)
    text = afk.t(
        "progress.line",
        steps=steps,
        word=afk.plural_word(
            steps, "progress.step_one", "progress.step_few", "progress.step_many"
        ),
        elapsed=afk.format_elapsed(now - float(state.get("last_reply_at") or now)),
        tool=tool_name,
        detail=(": " + detail) if detail else "",
    )
    afk.edit_message(config["bot_token"], config["chat_id"], message_id, text)
    afk.persist(state)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception as exc:
        afk.log("progress hook crashed: %r" % (exc,))
        sys.exit(0)
