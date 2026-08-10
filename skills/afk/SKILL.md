---
name: afk
description: Hands the current conversation over to Telegram when the user steps away from the computer — their replies from Telegram become the next turns in this same session, and permission requests are answered from the phone. Use when they say "/afk", "I need to step away", "going afk", "continue in Telegram", "text me on my phone", "switch afk on", and likewise "/afk off", "I'm back", "switch afk off". Not for one-off task-finished notifications, and not for sending messages to other people.
---

# AFK: the conversation continues in Telegram

The user walks away from the keyboard; the session keeps running. Every turn
you finish is delivered to their Telegram, and their reply comes back into this
same session as the next turn. Nothing is lost and they can keep working from a
phone.

## How it works (one paragraph)

After each turn the `Stop` hook sends your answer to Telegram and long-polls for
a message back; the text it receives is returned as `decision: block`, which the
runtime feeds in as a new user turn. While a turn is running, the `PostToolUse`
hook edits a single live ticker message ("⏳ Working… · N steps · time") that is
deleted right before the answer is sent. The `PermissionRequest` hook asks for
tool approval over the same channel. While AFK is off, every hook exits
immediately and does nothing.

## Switching it on

1. Check the setup:

   ```bash
   python3 <skill-dir>/scripts/afk_ctl.py status
   ```

2. If the bot is **not configured** — do not ask for the token in chat and do
   not put it in a command. Tell the user to run setup themselves in their own
   terminal:

   ```bash
   python3 <skill-dir>/scripts/afk_setup.py
   ```

   They need a bot first: Telegram → @BotFather → `/newbot` → then open the bot
   and press Start. The script hides the token input, validates it, discovers
   the chat id, sends a test message and stores the config with mode 0600.
   Then stop and wait until they confirm setup is done.

3. If the bot is configured, switch AFK on:

   ```bash
   python3 <skill-dir>/scripts/afk_ctl.py on
   ```

   Options: `--hours 8` (session cap), `--max-turns 40` (exchange budget),
   `--wait-minutes 45` (how long to wait for one reply).

4. Confirm briefly, then **carry on with whatever task was already running**.
   Do not wait for a separate instruction: the next turn you finish becomes the
   first Telegram message.

`<skill-dir>` is this skill's own directory, given to you when the skill is
invoked.

## While AFK is on

Your answers are read on a phone, so write accordingly:

- up to ~1500 characters, no long code listings or wide tables;
- one question at a time, answerable in a single line;
- if a decision is needed, propose one concrete option and ask briefly;
- when a meaningful chunk is done, say so — that is their checkpoint.

The usual safety rules still apply: irreversible actions (deploy, send, delete,
pay) still need confirmation — it just arrives from Telegram now.

## Switching it off

```bash
python3 <skill-dir>/scripts/afk_ctl.py off
```

The user can also switch it off from Telegram with `/back`. AFK additionally
switches itself off on the turn budget, on the session cap, and when no reply
arrives within `--wait-minutes`.

## Telegram commands

| Message | Effect |
|---|---|
| plain text | becomes the next turn in the session |
| `yes` / `no` | answers a permission request |
| `/status` | project, turn number, time left |
| `/back` | switch AFK off |

## What this skill does not do

- It does not stream reasoning: only the ticker moves in real time; the answer
  itself is sent when the turn is **finished**.
- It does not wake a session that has already stopped. A reply sent after AFK
  timed out simply sits unread in the chat.
- It does not work in background or scheduled runs — there is no one to talk to.

Details, limits and troubleshooting live in the repository `docs/`.
