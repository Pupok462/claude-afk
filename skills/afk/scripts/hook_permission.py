#!/usr/bin/env python3
"""PermissionRequest hook: approve or refuse tool calls from Telegram.

Without this, the first tool call needing approval freezes the session while
you are away and the whole AFK idea collapses. Every approval is still an
explicit human "yes" — this relays the prompt, it does not auto-approve.
"""

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import afk_common as afk  # noqa: E402

PREVIEW_LIMIT = 900


def allow():
    afk.emit(
        {
            "hookSpecificOutput": {
                "hookEventName": "PermissionRequest",
                "decision": {"behavior": "allow"},
            }
        }
    )


def deny(message):
    afk.emit(
        {
            "hookSpecificOutput": {
                "hookEventName": "PermissionRequest",
                "decision": {"behavior": "deny", "message": message},
            }
        }
    )


def main():
    raw = sys.stdin.read()
    try:
        event = json.loads(raw) if raw.strip() else {}
    except ValueError:
        event = {}

    session_id = event.get("session_id") or ""
    state = afk.active_state(session_id)
    if state is None:
        return 0  # AFK off — leave the normal on-screen prompt alone.

    config = afk.load_config()
    if not config:
        return 0

    token = config["bot_token"]
    chat_id = config["chat_id"]
    tool_name = event.get("tool_name") or "?"
    detail = afk.describe_tool(
        tool_name, event.get("tool_input"), limit=PREVIEW_LIMIT, collapse=False
    )

    # The progress ticker is left alone on purpose: it is an older message, so
    # the question still lands last, and the ticker survives for the rest of
    # the turn once the answer comes back.
    afk.send(token, chat_id, afk.t("perm.ask", tool=tool_name, detail=detail))

    wait_seconds = int(afk.setting(state, "permission_wait_seconds"))
    deadline = min(time.time() + wait_seconds, float(state["hard_deadline"]))

    while True:
        reply, _ = afk.wait_for_reply(token, chat_id, state, deadline)

        if reply is None:
            afk.send(token, chat_id, afk.t("perm.timeout"))
            afk.log("permission: timed out on %s, falling back to on-screen prompt" % tool_name)
            return 0  # no output: the normal prompt takes over

        lowered = reply.strip().lower()

        if lowered in afk.YES_WORDS:
            afk.log("permission: allowed %s from Telegram" % tool_name)
            allow()

        if lowered in afk.NO_WORDS:
            afk.log("permission: denied %s from Telegram" % tool_name)
            deny(afk.t("perm.denied"))

        if lowered in afk.STOP_WORDS:
            afk.send(token, chat_id, afk.t("perm.stopped"))
            afk.disable("stopped from Telegram during permission ask")
            return 0

        afk.send(token, chat_id, afk.t("perm.unclear", tool=tool_name))


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception as exc:
        afk.log("permission hook crashed: %r" % (exc,))
        sys.exit(0)
