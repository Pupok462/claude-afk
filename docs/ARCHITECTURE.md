# Architecture

## The one idea

A Claude Code `Stop` hook can refuse to let the turn end. When it returns

```json
{"decision": "block", "reason": "<text>"}
```

the runtime feeds `<text>` back into the **same session** as the next user turn.
That is the whole bridge: the hook sends the finished answer to Telegram, waits
for a message back, and hands that message to the runtime as the next turn.

There is no second Claude, no separate prompt, no API call, no new session. The
context window, project instructions, skills, tools and model are identical to
the ones you were using at the keyboard.

## Turn lifecycle

```
                ┌─────────────────────────── the session ──────────────────────────┐
                │                                                                  │
 you (phone) ──►│  Stop hook resumes, injects your text as the next turn            │
                │            │                                                      │
                │            ▼                                                      │
                │  Claude works ──► PostToolUse hook edits the ticker (throttled 4s) │
                │            │                                                      │
                │            ├──► PermissionRequest hook ──► "yes/no?" ──► you       │
                │            │                                                      │
                │            ▼                                                      │
                │  turn ends ──► Stop hook: delete ticker, send answer, long-poll ──►│──► you
                └──────────────────────────────────────────────────────────────────┘
```

## Files

```
skills/afk/
├── SKILL.md                  what Claude reads when you type /afk
├── i18n/{en,ru}.json         every user-facing string
└── scripts/
    ├── afk_common.py         config, state, Telegram client, i18n
    ├── afk_ctl.py            on / off / status  (run by Claude)
    ├── afk_setup.py          one-time bot setup   (run by you)
    ├── hook_stop.py          Stop            — the bridge itself
    ├── hook_progress.py      PostToolUse     — the live ticker
    ├── hook_permission.py    PermissionRequest — remote approvals
    └── hook_notify.py        Notification    — "the session needs you"
hooks/hooks.json              registers all four hooks on plugin install
```

## State

Two files under `~/.claude/afk/` (mode `0600`, override with `AFK_HOME`):

- **`config.json`** — `bot_token`, `chat_id`, `lang`. Written by setup, never
  printed back.
- **`active.json`** — exists only while AFK is on. Deleting it switches
  everything off; that is why the hooks are cheap when idle.

`active.json` fields:

| Field | Purpose |
|---|---|
| `enabled` | master switch |
| `started_at` | anything older is a stale backlog and is dropped |
| `hard_deadline` | wall-clock cap for the whole AFK session |
| `bound_session_id` | claimed by the first hook that runs; other sessions are ignored |
| `turns`, `max_turns` | runaway budget |
| `offset` | Telegram `getUpdates` cursor, persisted every round |
| `status_message_id` | the ticker being edited, `null` when nothing is in flight |
| `progress_steps`, `last_progress_at` | ticker counter and throttle |

## Design decisions worth knowing

**Hooks are always installed, gated by a file.** `Stop` and `PostToolUse` have
no matcher support worth using, so they fire on every turn and every tool call.
The first thing each does is check for `active.json`; `hook_progress.py` does it
before even importing the shared module, because it runs after *every* tool
call.

**The session binds on first use.** `/afk` writes `bound_session_id: null`; the
first hook to run claims it. This avoids needing to know the session id at
switch-on time and stops a second window from stealing the bridge.

**One ticker, edited in place.** A message per tool call would be unreadable on
a phone. Edits are throttled to one per 4 seconds, and Telegram's "message is
not modified" error is treated as success.

**The answer is a new message, not an edit.** Editing does not trigger a
notification. The ticker is deleted first so the chat ends up clean.

**Everything fails open.** Every hook wraps `main()` and exits `0` on any
exception, logging to `~/.claude/afk/afk.log`. A dead bridge must never wedge a
session — the worst case is silence on the phone.

**Permission timeout does not deny.** If nobody answers, the hook emits nothing
and the normal on-screen prompt takes over. Denying by default would break work
you were happy to approve.

## Why not a daemon

A background service could wake a session that has already stopped — the one
capability this design lacks. It would also mean a supervised process, a Node or
Python runtime on `PATH`, an update story, and something to debug when it dies.
For "I stepped away for twenty minutes", four hooks that cost nothing when idle
are a better trade. If waking a dead session matters to you, the alternatives in
the README do it with keystroke injection into tmux.
