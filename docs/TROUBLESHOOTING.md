# Troubleshooting

Start here, always:

```bash
python3 skills/afk/scripts/afk_ctl.py status
tail -30 ~/.claude/afk/afk.log
```

Every hook logs its decisions and every failure to that file.

## Nothing arrives in Telegram

**`status` says the bot is NOT configured** — setup has not run, or it wrote to
a different home. Run `afk_setup.py` from your own terminal. If you use
`AFK_HOME`, it must be set the same way for setup and for Claude Code.

**`status` says AFK is on, but the chat is silent** — the `Stop` hook only fires
when a turn *finishes*. If Claude is still working, or is waiting on an on-screen
permission prompt, nothing has been sent yet. Check the log for `send failed`.

**The log shows `send failed: sendMessage -> ... chat not found`** — the
`chat_id` is wrong, or you never pressed Start on the bot. Message the bot, then
re-run setup.

**The log shows `Unauthorized`** — the token was revoked or mistyped. Get a new
one from @BotFather and re-run setup.

## Messages arrive but replies do nothing

**You replied after the wait ran out.** The default is 45 minutes; after that
the turn ends and AFK switches off. The log will show `no reply before deadline`.
Switch AFK on again.

**You are writing from a different Telegram account** (for example a second
device signed in as someone else). The log will show `ignored message from
unauthorized chat <id>`. Only the configured `chat_id` is accepted.

**Another Claude Code window claimed the bridge.** `status` shows `bound to
session`. Switch AFK off and on in the window you actually want.

## The session is stuck and Telegram is quiet

A permission dialog that is not covered by the `Notification` matcher can leave
the session waiting on screen. Look for `permission: timed out` in the log. Go
to the keyboard and answer it; consider raising `permission_wait_seconds` in
`~/.claude/afk/config.json`.

## The ticker misbehaves

**It never appears** — the ticker only exists for turns started *from Telegram*.
A turn you started at the keyboard has no ticker by design.

**It froze on one step** — the ticker updates on tool calls. If Claude is
thinking without calling tools, it will sit still; the elapsed time does not
tick on its own.

**It stayed behind after the turn** — a turn interrupted mid-flight (Esc) skips
the cleanup. `afk_ctl.py off` deletes it.

## Hooks do not run at all

1. Confirm the plugin is installed and enabled.
2. Confirm the scripts are executable: `chmod +x skills/afk/scripts/*.py`.
3. Confirm `python3` resolves in the environment Claude Code runs hooks in:
   `echo '{}' | skills/afk/scripts/hook_stop.py; echo $?` should print `0`.
4. Run `claude --debug` and look for hook errors.

## Everything is fine but you want it gone

Uninstall the plugin, then remove the state:

```bash
rm -rf ~/.claude/afk
```

That deletes the bot token and the log. Revoke the token in @BotFather too if
you are done with the bot.
