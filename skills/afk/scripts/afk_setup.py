#!/usr/bin/env python3
"""One-time bot setup. RUN THIS YOURSELF in a terminal, not through Claude.

The token is read with getpass so it never appears on screen, in shell history,
in a command line, or in an AI transcript. It is stored in
~/.claude/afk/config.json with mode 0600 and never printed back.
"""

import getpass
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import afk_common as afk  # noqa: E402


def fail(message):
    print("\n✗ %s" % message)
    return 1


def discover_chat(token, attempts=20):
    """Poll getUpdates until the user writes to the bot."""
    offset = 0
    for _ in range(attempts):
        try:
            updates = afk.tg_call(
                token, "getUpdates", {"offset": offset, "timeout": 3}, timeout=20
            )
        except afk.TelegramError as exc:
            if "webhook" in str(exc).lower():
                print(afk.t("setup.webhook"))
                return ""
            print("  ! %s" % exc)
            return ""
        for update in updates or []:
            offset = max(offset, int(update.get("update_id", 0)) + 1)
            chat = (update.get("message") or {}).get("chat") or {}
            if chat.get("id") is not None:
                who = chat.get("username") or chat.get("first_name") or chat.get("id")
                print(afk.t("setup.found", who=who))
                return str(chat["id"])
        sys.stdout.write(".")
        sys.stdout.flush()
    print("")
    return ""


def main():
    print(afk.t("setup.intro"))
    token = getpass.getpass(afk.t("setup.prompt_token")).strip()
    if not token or ":" not in token:
        return fail(afk.t("setup.bad_token"))

    try:
        me = afk.tg_call(token, "getMe", timeout=20)
    except afk.TelegramError as exc:
        return fail(afk.t("setup.rejected", error=exc))
    print(afk.t("setup.connected", username=me.get("username")))

    chat_id = (os.environ.get("AFK_CHAT_ID") or "").strip()
    if not chat_id:
        print(afk.t("setup.looking"))
        chat_id = discover_chat(token)
    if not chat_id:
        chat_id = input(afk.t("setup.manual")).strip()
    if not chat_id:
        return fail(afk.t("setup.no_chat"))

    try:
        afk.tg_call(
            token,
            "sendMessage",
            {"chat_id": chat_id, "text": afk.t("setup.test_message")},
            timeout=20,
        )
    except afk.TelegramError as exc:
        return fail(afk.t("setup.test_failed", error=exc))

    afk.write_json_atomic(
        afk.CONFIG_PATH,
        {
            "bot_token": token,
            "chat_id": str(chat_id),
            "bot_username": me.get("username"),
            "lang": os.environ.get("AFK_LANG") or afk._detect_lang(),
            "configured_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "offset": 0,
        },
    )
    print(afk.t("setup.done", path=afk.CONFIG_PATH))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print(afk.t("setup.cancelled"))
        sys.exit(1)
