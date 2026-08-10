# Contributing

## Ground rules

**Zero runtime dependencies.** The bridge runs as Claude Code hooks, on whatever
Python the user happens to have. Standard library only, Python 3.9+. No
`requests`, no `python-telegram-bot`, no virtualenv assumptions. A pull request
that adds a dependency needs a very good reason.

**Hooks fail open.** Every hook wraps its work and exits `0` on any exception,
logging to `~/.claude/afk/afk.log`. A bug in this project must never wedge
someone's session. Never let an exception escape `main()`.

**No user-facing string in code.** Everything the user reads goes in
`skills/afk/i18n/*.json` and is fetched with `afk.t("key")`.

## Running the tests

```bash
python3 tests/test_bridge.py
```

38 end-to-end checks against a local stub of the Telegram Bot API on an
ephemeral port. No network, no bot token, no account. The suite runs the real
hook scripts as subprocesses, which is the only way to test the parts that
matter — the JSON contract with the runtime.

Add a check for anything you change. `check(name, condition, detail)` prints
`PASS`/`FAIL` and the runner exits non-zero if anything failed, which is what CI
reads.

Deliberately not pytest: a project whose whole pitch is "no dependencies" should
not need a test dependency to verify itself.

## Adding a language

1. Copy `skills/afk/i18n/en.json` to `<code>.json` (an ISO 639-1 code).
2. Translate the values. Keep the `{placeholders}` intact.
3. Missing keys fall back to English individually, so a partial file is fine.
4. Test it: `AFK_LANG=<code> python3 tests/test_bridge.py`.

Plural forms use Slavic rules (`progress.step_one` / `_few` / `_many`), which
also produce correct output for two-form languages — set `_few` and `_many` to
the same string.

## Touching the hook contract

The JSON that hooks exchange with Claude Code is the load-bearing part:

- `Stop` → `{"decision": "block", "reason": "..."}` continues the conversation.
- `PermissionRequest` →
  `{"hookSpecificOutput": {"hookEventName": "PermissionRequest", "decision": {"behavior": "allow"|"deny"}}}`.

If you change either, verify against the current
[hooks reference](https://code.claude.com/docs/en/hooks) — not from memory —
and say in the PR which version you checked against.

## Pull requests

- One change per PR.
- Explain the behaviour, not the diff.
- Say what you tested and paste the test summary line.
- Screenshots of the Telegram side are very welcome for UX changes.
