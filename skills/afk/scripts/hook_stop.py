#!/usr/bin/env python3
"""Stop hook: relay the finished turn to Telegram and wait for the reply.

When AFK is off this exits in milliseconds. When it is on, the reply that comes
back from Telegram is returned as `decision: block`, which Claude Code feeds in
as the next user turn — that is what keeps the conversation going off-desk.
"""

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import afk_common as afk  # noqa: E402


def main():
    raw = sys.stdin.read()
    try:
        event = json.loads(raw) if raw.strip() else {}
    except ValueError:
        event = {}

    session_id = event.get("session_id") or ""
    state = afk.active_state(session_id)
    if state is None:
        return 0  # AFK off, or another session owns it — fast path.

    config = afk.load_config()
    if not config:
        afk.log("stop: AFK on but config missing; disabling")
        afk.disable("config missing")
        return 0

    token = config["bot_token"]
    chat_id = config["chat_id"]

    turns = int(state.get("turns", 0))
    max_turns = int(afk.setting(state, "max_turns"))
    project = os.path.basename(event.get("cwd") or state.get("cwd") or "") or "claude"
    body = (event.get("last_assistant_message") or "").strip()

    # The live status message has done its job — the real answer replaces it.
    afk.clear_status(token, chat_id, state)

    header = afk.t("stop.header", project=project, turn=turns + 1, max=max_turns)
    afk.send(token, chat_id, "%s\n\n%s" % (header, body or afk.t("stop.empty")))

    if turns >= max_turns:
        afk.send(token, chat_id, afk.t("stop.turn_limit", max=max_turns))
        afk.disable("turn budget exhausted")
        return 0

    wait_seconds = int(afk.setting(state, "wait_seconds"))
    deadline = min(time.time() + wait_seconds, float(state["hard_deadline"]))

    while True:
        reply, _ = afk.wait_for_reply(token, chat_id, state, deadline)

        if reply is None:
            afk.send(token, chat_id, afk.t("stop.no_reply", minutes=wait_seconds // 60))
            afk.disable("no reply before deadline")
            return 0

        lowered = reply.strip().lower()

        if lowered in afk.STOP_WORDS:
            afk.send(token, chat_id, afk.t("stop.stopped"))
            afk.disable("stopped from Telegram")
            return 0

        if lowered in afk.STATUS_WORDS:
            left = int((float(state["hard_deadline"]) - time.time()) / 60)
            afk.send(
                token,
                chat_id,
                afk.t(
                    "stop.status",
                    project=project,
                    turn=turns + 1,
                    max=max_turns,
                    minutes=left,
                ),
            )
            continue  # keep waiting for a real instruction

        state["turns"] = turns + 1
        state["last_reply_at"] = time.time()
        # Acknowledge instantly, then let hook_progress.py edit this same
        # message as tools run — otherwise the phone sees silence until the
        # turn ends.
        state["progress_steps"] = 0
        state["last_progress_at"] = 0
        state["status_message_id"] = afk.send_returning_id(
            token, chat_id, afk.t("stop.ack")
        )
        afk.persist(state)
        afk.log("stop: injecting reply (%d chars) into session %s" % (len(reply), session_id))
        afk.emit({"decision": "block", "reason": afk.t("stop.continue", reply=reply)})


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception as exc:  # fail open: a broken bridge must never wedge the session
        afk.log("stop hook crashed: %r" % (exc,))
        sys.exit(0)
