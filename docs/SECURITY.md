# Security

## The trade-off, stated once

When AFK is on, a Telegram message becomes a turn in your Claude Code session,
and `yes` approves a tool call. **Whoever controls your Telegram account
controls that session.** That is not a bug to be fixed; it is the feature.

Reasonable precautions:

- a device lock on the phone that has Telegram;
- [two-step verification](https://telegram.org/faq#q-how-do-i-set-up-2-step-verification)
  on the Telegram account;
- switch AFK off when you are back — `/back` from the phone or `/afk off` at the
  keyboard. It also expires on its own.

## What the bridge does to limit damage

| Control | Behaviour |
|---|---|
| Chat allowlist | Only the configured `chat_id` is read. Messages from any other chat are logged and dropped. |
| Stale-message guard | The update queue is drained when AFK starts, and anything with a timestamp older than `started_at` is discarded — a backlog cannot be replayed as instructions. |
| Turn budget | `--max-turns` (default 40) caps exchanges per session. |
| Wall-clock cap | `--hours` (default 8) switches AFK off unconditionally. |
| Reply timeout | `--wait-minutes` (default 45) ends the turn if nobody answers. |
| Fail-open hooks | Any exception is logged and the hook exits `0`. |
| No auto-approval | Permission requests are relayed. A timeout falls back to the on-screen prompt rather than allowing or denying. |

Your existing `PreToolUse` hooks still run. Approving from Telegram does not
bypass anything you already have guarding commits, pushes or destructive
commands.

## Token handling

The bot token is a password for the bot. This project never puts it anywhere
that leaks:

- `afk_setup.py` reads it with `getpass` — not echoed, not in shell history, not
  in `ps`, not in a command line, and **not in an AI chat transcript**;
- it is stored in `~/.claude/afk/config.json` with mode `0600`;
- it is never printed back, and the `.gitignore` refuses `config.json`.

**Never paste a token into a chat with an AI assistant.** Transcripts get
stored, and are often ingested by memory or observability tooling. If a token
was exposed, revoke it: @BotFather → `/revoke` → then re-run `afk_setup.py`.

## What is sent to Telegram

Everything you would have seen on screen at the end of a turn: the assistant's
answer, the name and preview of a tool call awaiting permission, and a one-line
ticker naming the current tool. That can include file paths, commands, and
snippets of your code.

Telegram messages are not end-to-end encrypted in regular chats. If a repository
is sensitive enough that its file paths should not sit on Telegram's servers, do
not use AFK on it.

## Reporting a vulnerability

Open an issue for anything non-sensitive. For a real vulnerability, use GitHub's
private security advisory on the repository rather than a public issue.
