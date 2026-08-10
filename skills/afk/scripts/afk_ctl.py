#!/usr/bin/env python3
"""Turn AFK mode on/off and report status. Claude runs this when you type /afk.

The hooks are always installed but do nothing unless the state file written
here exists, so switching modes is just creating or deleting one file.
"""

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import afk_common as afk  # noqa: E402


def cmd_on(args):
    config = afk.load_config()
    if not config:
        print(afk.t("ctl.setup_hint", setup=afk.SETUP_SCRIPT))
        return 2

    token = config["bot_token"]
    chat_id = config["chat_id"]

    # Drop anything typed before AFK started so old chatter is never injected.
    offset = afk.drain(token, chat_id, int(config.get("offset", 0)))

    now = time.time()
    state = {
        "enabled": True,
        "started_at": now,
        "hard_deadline": now + args.hours * 3600,
        "cwd": os.getcwd(),
        "session_ids": [
            os.environ.get("CLAUDE_CODE_SESSION_ID", ""),
            os.environ.get("CLAUDE_CODE_HOST_SESSION_ID", ""),
        ],
        "bound_session_id": None,
        "turns": 0,
        "offset": offset,
        "max_turns": args.max_turns,
        "wait_seconds": args.wait_minutes * 60,
        "permission_wait_seconds": afk.DEFAULTS["permission_wait_seconds"],
    }
    afk.persist(state)
    afk.log("AFK enabled in %s" % state["cwd"])

    afk.send(
        token,
        chat_id,
        afk.t(
            "ctl.started",
            project=os.path.basename(state["cwd"]) or "claude",
            max_turns=args.max_turns,
            wait=args.wait_minutes,
            hours=args.hours,
        ),
    )
    print(
        afk.t(
            "ctl.on_summary",
            cwd=state["cwd"],
            max_turns=args.max_turns,
            wait=args.wait_minutes,
            hours=args.hours,
        )
    )
    return 0


def cmd_off(_args):
    state = afk.load_state()
    config = afk.load_config()
    if state and config:
        # A turn interrupted mid-flight can leave a live ticker behind.
        afk.clear_status(config["bot_token"], config["chat_id"], state)
        afk.send(config["bot_token"], config["chat_id"], afk.t("ctl.stopped"))
    afk.disable("turned off via afk_ctl")
    print(afk.t("ctl.off_summary") if state else afk.t("ctl.already_off"))
    return 0


def cmd_status(_args):
    state = afk.load_state()
    config = afk.load_config()
    print(
        afk.t(
            "ctl.status_bot",
            state=afk.t("ctl.status_bot_ok" if config else "ctl.status_bot_missing"),
        )
    )
    if not state or not state.get("enabled"):
        print(afk.t("ctl.status_off"))
        return 0
    print(
        afk.t(
            "ctl.status_on",
            cwd=state.get("cwd"),
            turns=state.get("turns"),
            max_turns=state.get("max_turns"),
            session=state.get("bound_session_id") or afk.t("ctl.status_unbound"),
            minutes=int((float(state.get("hard_deadline", 0)) - time.time()) / 60),
        )
    )
    return 0


def main():
    parser = argparse.ArgumentParser(description="AFK Telegram bridge control")
    sub = parser.add_subparsers(dest="command")

    on = sub.add_parser("on", help="switch AFK on")
    on.add_argument("--hours", type=float, default=afk.DEFAULTS["session_hours"])
    on.add_argument("--max-turns", type=int, default=afk.DEFAULTS["max_turns"])
    on.add_argument(
        "--wait-minutes", type=int, default=afk.DEFAULTS["wait_seconds"] // 60
    )
    on.set_defaults(func=cmd_on)

    sub.add_parser("off", help="switch AFK off").set_defaults(func=cmd_off)
    sub.add_parser("status", help="show current state").set_defaults(func=cmd_status)

    args = parser.parse_args()
    if not getattr(args, "func", None):
        parser.print_help()
        return 1
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
