# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] — 2026-08-11

First public release.

### Added

- **Turn relay over Telegram.** A `Stop` hook sends each finished turn to
  Telegram and long-polls for a reply, which is returned as
  `decision: block` — the runtime feeds it back into the same live session.
- **Remote permission approvals.** A `PermissionRequest` hook relays tool calls
  to the phone and answers `allow` / `deny` from a `yes` / `no`. A timeout falls
  back to the on-screen prompt instead of deciding for you.
- **Live progress ticker.** A `PostToolUse` hook edits one message in place
  ("⏳ Working… · N steps · time · tool"), throttled to one edit per 4 seconds
  and deleted before the answer is sent.
- **Idle notifications.** A `Notification` hook (matcher `idle_prompt`,
  `agent_needs_input`) reports that the session needs attention.
- **Plugin packaging.** `hooks/hooks.json` registers all four hooks on install —
  no manual `settings.json` editing.
- **Localisation.** All user-facing strings in `skills/afk/i18n/`; English and
  Russian shipped, per-key fallback to English, selected by config or `AFK_LANG`.
- **Safety budgets.** Chat allowlist, stale-backlog rejection, turn budget,
  per-reply wait, hard session cap, and fail-open hooks that log and exit `0`.
- **Setup script** reading the bot token with `getpass` and storing it `0600`.
- **38 end-to-end tests** against a local stub of the Telegram Bot API — no
  network, no account, no dependencies.
- Documentation: README (English and Russian), architecture, security and
  troubleshooting guides.

[0.1.0]: https://github.com/Pupok462/claude-afk/releases/tag/v0.1.0
