# claude-afk

**Walk away from your desk without ending the conversation.** Type `/afk` and
your live Claude Code session keeps going in Telegram: finished turns arrive on
your phone, your replies come back as the next turn, tool approvals are a
`yes`/`no`, and a live ticker shows what is running right now.

No daemon. No tmux. No Node. No dependencies — pure Python standard library.

[Русская версия](README.ru.md)

---

## What it looks like

```
you:  fix the failing tests
      ⏳ Got it, working…                        ← arrives instantly
      ⏳ Working… · 1 step · 2s
      └ Bash: pytest tests/ -q                   ← same message, edited in place
      ⏳ Working… · 7 steps · 1m 12s
      └ Read: src/conftest.py
                                                 ← deleted
      🤖 demo · turn 3/40
      Fixed — the fixture was leaking a temp dir…  ← new message, so it notifies

      🔐 Permission requested
      Tool: Bash
      git push origin main
      Reply: yes / no
you:  yes
```

One message is edited in place while work happens, so the chat never fills with
noise. The answer is sent as a *new* message on purpose — editing an old one
would not raise a notification, and the finished turn is exactly what you want
to be notified about.

## Why this exists

Plenty of projects put Claude Code in Telegram. Almost all of them own the
agent process: they spawn it, or drive a `tmux` pane with keystroke injection.
That is a great fit for a terminal workflow on a VPS.

`claude-afk` takes the other approach — it hooks into **the interactive session
you are already sitting in front of**. You hand the conversation over mid-task
and take it back at the keyboard, with full context on both sides. It works in
the Claude Code desktop app, where there is no tmux pane to type into, and it
adds nothing to your machine except four Python files that exit in milliseconds
when AFK is off.

Honest comparison with the alternatives is [further down](#alternatives).

## Install

```bash
/plugin marketplace add Pupok462/claude-afk
```

```bash
/plugin install claude-afk@claude-afk-marketplace
```

The plugin ships its own hooks, so there is nothing to paste into
`settings.json`.

### Connect a bot (once, ~2 minutes)

1. In Telegram, open [@BotFather](https://t.me/BotFather) → `/newbot` → pick a
   name and a username ending in `bot`.
2. Open your new bot, press **Start**, and send it any message. A bot cannot
   message you first — Telegram forbids it.
3. In **your own terminal** (not through Claude — the token must not land in an
   AI transcript):

   ```bash
   python3 ~/.claude/plugins/*/claude-afk/*/skills/afk/scripts/afk_setup.py
   ```

   The token input is hidden. The script validates it, finds your chat id,
   sends a test message, and writes `~/.claude/afk/config.json` with mode
   `0600`.

Running from a clone instead? Use `skills/afk/scripts/afk_setup.py`.

## Use

In Claude Code, type `/afk` — or just say "I need to step away". Then leave.

| In Telegram | Effect |
|---|---|
| plain text | becomes the next turn in the session |
| `yes` / `no` | answers a permission request |
| `/status` | project, turn number, time left |
| `/back` | switch AFK off |

Back at the keyboard: `/afk off`.

Options when switching on: `--hours 8` (session cap), `--max-turns 40`
(exchange budget), `--wait-minutes 45` (how long one turn waits for a reply).

## How it works

```
        turn finished
Claude ──────────────► Stop hook ──► sendMessage ──► Telegram
                          │                             │
                          │       long-poll getUpdates  │
                          ◄─────────────────────────────┘
                          │
              {"decision":"block","reason":"<your text>"}
                          │
                          ▼
            the runtime feeds that in as the next user turn
```

Four hooks, all switched by one state file (`~/.claude/afk/active.json`):

| Hook | Job | Timeout |
|---|---|---|
| `Stop` | delete the ticker, send the finished turn, wait for a reply, return it to the session | 3600 s |
| `PostToolUse` | edit the live ticker after each tool call | 20 s |
| `PermissionRequest` | ask `yes`/`no` for a tool call | 1200 s |
| `Notification` | say that the session needs attention (`idle_prompt`, `agent_needs_input`) | 30 s |

The state binds to the first session that runs a hook, so a second Claude Code
window is never hijacked. Full details in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Limits — stated plainly

- **Answer granularity is a turn.** The ticker moves in real time; the answer
  itself arrives when the turn is finished. Reasoning is not streamed.
- **The session must stay alive.** This lives inside a running Claude Code
  session — close it and the bridge goes with it.
- **A reply after the timeout is not picked up.** If nobody answers within
  `--wait-minutes` (45 by default), the turn ends and AFK switches off. Your
  message stays in the chat but will not enter the session.
- **Not for background or scheduled runs.** There is nobody to hold a
  conversation with.

## Safety

- Only the configured `chat_id` is accepted; anything else is logged and
  dropped.
- Messages sent *before* AFK was switched on are never injected: the update
  queue is drained at start and anything older than the start time is discarded.
- Budgets: turn count, per-reply wait, and a hard wall-clock session cap.
- Any error inside a hook is logged and the hook exits `0` — a broken bridge
  can never wedge your session.
- Tool approvals are relayed, never auto-granted. Each one is an explicit human
  `yes`.

**Understand the trade-off:** approving tool calls from a phone means whoever
controls your Telegram account controls your Claude Code session. Use a device
lock and Telegram two-step verification. More in [docs/SECURITY.md](docs/SECURITY.md).

## Configuration

`~/.claude/afk/config.json` (mode `0600`, created by setup):

| Key | Meaning |
|---|---|
| `bot_token` | from @BotFather |
| `chat_id` | the only chat allowed to drive the session |
| `lang` | interface language — `en`, `ru`, or any file in `skills/afk/i18n/` |

Environment overrides: `AFK_LANG`, `AFK_HOME` (state directory),
`AFK_TG_API_BASE` (used by the test stub).

Adding a language is a JSON file in `skills/afk/i18n/` — missing keys fall back
to English per key, so a partial translation is fine.

## Tests

38 end-to-end checks against a local stub of the Telegram API. No network, no
Telegram account, no dependencies:

```bash
python3 tests/test_bridge.py
```

They run the real hook scripts as subprocesses, exactly as Claude Code does,
and cover delivery, reply injection, session binding, `/back`, timeouts,
foreign-chat rejection, stale backlogs, message chunking, permission
allow/deny, the turn budget, corrupt state, the ticker lifecycle, and locale
fallback.

## Alternatives

Worth knowing before you pick this one:

- [jsayubi/ccgram](https://github.com/jsayubi/ccgram) — the closest sibling.
  Also hook-based, plus inline buttons (Allow/Deny/**Always**/Defer), keystroke
  injection into tmux/Ghostty/PTY, and a supervised background service. Node 18+.
- [alexei-led/ccgram](https://github.com/alexei-led/ccgram) — tmux/herdr bridge
  covering Claude Code, Codex and Gemini, parallel sessions as Telegram topics,
  voice input. Python 3.14+ and tmux required.
- [oscarsterling/claude-telegram-remote](https://github.com/oscarsterling/claude-telegram-remote) —
  23 commands, checkpoint rollback; needs tmux, two bots and an MCP plugin.
- [Open-ACP/OpenACP](https://github.com/Open-ACP/OpenACP) — Agent Client
  Protocol bridge to Telegram, Discord and Slack.
- [RichardAtCT/claude-code-telegram](https://github.com/RichardAtCT/claude-code-telegram) —
  the long-standing full remote-access bot.

Pick `claude-afk` if you want the desktop app supported, zero dependencies, and
a handoff of the session you are already in. Pick one of the others if you live
in tmux and want buttons and keystroke control.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Translations and hook-edge-case tests
are especially welcome.

## License

MIT — see [LICENSE](LICENSE).
