"""Shared helpers for the AFK Telegram bridge.

Standard library only, Python 3.9+: these run as Claude Code hooks and must
work without a virtualenv, a package manager, or a network dependency.
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request

HOME = os.path.expanduser("~")
# AFK_HOME is an override for the test harness; normal runs use ~/.claude/afk.
AFK_DIR = os.environ.get("AFK_HOME") or os.path.join(HOME, ".claude", "afk")
CONFIG_PATH = os.path.join(AFK_DIR, "config.json")
STATE_PATH = os.path.join(AFK_DIR, "active.json")
LOG_PATH = os.path.join(AFK_DIR, "afk.log")

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(SCRIPTS_DIR)
I18N_DIR = os.path.join(SKILL_DIR, "i18n")
SETUP_SCRIPT = os.path.join(SCRIPTS_DIR, "afk_setup.py")

# Overridable so the test harness can point at a local stub instead of Telegram.
TG_API_BASE = os.environ.get("AFK_TG_API_BASE", "https://api.telegram.org")

TG_MAX_CHARS = 3900  # Telegram's hard limit is 4096; leave room for our prefix.

DEFAULTS = {
    "wait_seconds": 2700,  # how long one Stop hook waits for a reply (45 min)
    "permission_wait_seconds": 900,  # how long a permission ask waits (15 min)
    "max_turns": 40,  # runaway guard: AFK exchanges per session
    "session_hours": 8,  # hard wall-clock cap for one AFK session
    "poll_seconds": 50,  # Telegram long-poll window per request
}

# Both languages stay active regardless of the interface language: a Russian
# speaker may still type "yes" from a phone keyboard, and vice versa.
STOP_WORDS = {
    "/back", "/off", "/stop", "/quit", "/end",
    "back", "i'm back", "im back",
    "вернулся", "я тут", "я вернулся",
}
STATUS_WORDS = {"/status", "/статус"}
YES_WORDS = {
    "y", "yes", "ok", "okay", "sure", "go", "approve", "allow", "+", "/yes",
    "ок", "да", "давай", "разрешаю",
}
NO_WORDS = {
    "n", "no", "nope", "deny", "cancel", "-", "/no",
    "нет", "стоп", "не надо", "отмена",
}


# --------------------------------------------------------------------------
# Localisation
# --------------------------------------------------------------------------

_STRINGS = None


def _detect_lang():
    for var in ("AFK_LANG", "LC_ALL", "LC_MESSAGES", "LANG"):
        value = os.environ.get(var) or ""
        code = value.split(".")[0].split("_")[0].strip().lower()
        if code and os.path.exists(os.path.join(I18N_DIR, code + ".json")):
            return code
    return "en"


def _load_strings():
    global _STRINGS
    if _STRINGS is not None:
        return _STRINGS
    config = read_json(CONFIG_PATH) or {}
    lang = os.environ.get("AFK_LANG") or config.get("lang") or _detect_lang()
    # English is the base layer, so a partial translation degrades to English
    # per key instead of crashing on a missing one.
    strings = read_json(os.path.join(I18N_DIR, "en.json"), {}) or {}
    if lang != "en":
        strings.update(read_json(os.path.join(I18N_DIR, lang + ".json"), {}) or {})
    _STRINGS = strings
    return strings


def t(key, **kwargs):
    """Localised string by key. Falls back to the key itself if unknown."""
    template = _load_strings().get(key, key)
    try:
        return template.format(**kwargs)
    except (KeyError, IndexError, ValueError):
        return template


def plural_word(count, one_key, few_key, many_key):
    """Slavic plural rules, which also produce correct English (few == many)."""
    tail = count % 100
    if 11 <= tail <= 14:
        return t(many_key)
    tail = count % 10
    if tail == 1:
        return t(one_key)
    if 2 <= tail <= 4:
        return t(few_key)
    return t(many_key)


def format_elapsed(seconds):
    seconds = max(0, int(seconds))
    if seconds < 60:
        return "%ds" % seconds
    return "%dm %02ds" % (seconds // 60, seconds % 60)


# --------------------------------------------------------------------------
# Files and state
# --------------------------------------------------------------------------


def log(message):
    """Append a timestamped line to the AFK log. Never raises."""
    try:
        os.makedirs(AFK_DIR, mode=0o700, exist_ok=True)
        stamp = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(LOG_PATH, "a", encoding="utf-8") as fh:
            fh.write("%s %s\n" % (stamp, message))
    except Exception:
        pass


def read_json(path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return default


def write_json_atomic(path, data, mode=0o600):
    os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
    tmp = "%s.tmp.%d" % (path, os.getpid())
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    os.chmod(tmp, mode)
    os.replace(tmp, path)


def load_config():
    """Return the bot config, or None when setup has not run."""
    config = read_json(CONFIG_PATH)
    if not isinstance(config, dict):
        return None
    if not config.get("bot_token") or not config.get("chat_id"):
        return None
    return config


def load_state():
    state = read_json(STATE_PATH)
    return state if isinstance(state, dict) else None


def setting(state, key):
    """Per-session override, else global default."""
    if state and key in state:
        return state[key]
    return DEFAULTS[key]


def persist(state):
    try:
        write_json_atomic(STATE_PATH, state)
    except Exception as exc:
        log("state write failed: %s" % exc)


def disable(reason=""):
    """Turn AFK off by removing the state file."""
    try:
        if os.path.exists(STATE_PATH):
            os.remove(STATE_PATH)
        log("AFK disabled: %s" % (reason or "no reason given"))
    except Exception as exc:
        log("disable failed: %s" % exc)


def active_state(session_id):
    """Return the state dict when AFK is on and owns this session, else None.

    The first hook to run after /afk binds the state to its session, so a
    second Claude Code window is never hijacked.
    """
    state = load_state()
    if not state or not state.get("enabled"):
        return None
    if time.time() > float(state.get("hard_deadline", 0)):
        disable("hard deadline reached")
        return None
    bound = state.get("bound_session_id")
    if not bound:
        state["bound_session_id"] = session_id
        persist(state)
        return state
    if bound != session_id:
        return None
    return state


# --------------------------------------------------------------------------
# Telegram
# --------------------------------------------------------------------------


class TelegramError(Exception):
    pass


def tg_call(token, method, params=None, timeout=65):
    url = "%s/bot%s/%s" % (TG_API_BASE, token, method)
    body = json.dumps(params or {}).encode("utf-8")
    request = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", "replace")[:300]
        except Exception:
            pass
        raise TelegramError("%s -> HTTP %s %s" % (method, exc.code, detail))
    except Exception as exc:
        raise TelegramError("%s -> %s" % (method, exc))
    if not payload.get("ok"):
        raise TelegramError("%s -> %s" % (method, payload.get("description")))
    return payload.get("result")


def chunk(text, size=TG_MAX_CHARS):
    """Split long text on line boundaries so Telegram accepts it."""
    text = text or "…"
    if len(text) <= size:
        return [text]
    parts = []
    current = ""
    for line in text.splitlines(True):
        while len(line) > size:
            if current:
                parts.append(current)
                current = ""
            parts.append(line[:size])
            line = line[size:]
        if len(current) + len(line) > size:
            parts.append(current)
            current = line
        else:
            current += line
    if current:
        parts.append(current)
    return parts


def send(token, chat_id, text, timeout=20):
    """Send text to the AFK chat, splitting it if needed. True on success."""
    ok = True
    for part in chunk(text):
        try:
            tg_call(
                token,
                "sendMessage",
                {"chat_id": chat_id, "text": part, "disable_web_page_preview": True},
                timeout=timeout,
            )
        except TelegramError as exc:
            log("send failed: %s" % exc)
            ok = False
    return ok


def send_returning_id(token, chat_id, text, timeout=20):
    """Send one short message and return its message_id, or None on failure."""
    try:
        result = tg_call(
            token,
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": text[:TG_MAX_CHARS],
                "disable_web_page_preview": True,
            },
            timeout=timeout,
        )
        return (result or {}).get("message_id")
    except TelegramError as exc:
        log("status send failed: %s" % exc)
        return None


def edit_message(token, chat_id, message_id, text, timeout=15):
    try:
        tg_call(
            token,
            "editMessageText",
            {
                "chat_id": chat_id,
                "message_id": message_id,
                "text": text[:TG_MAX_CHARS],
                "disable_web_page_preview": True,
            },
            timeout=timeout,
        )
        return True
    except TelegramError as exc:
        # Telegram rejects an edit that would change nothing — not an error.
        if "not modified" in str(exc).lower():
            return True
        log("status edit failed: %s" % exc)
        return False


def delete_message(token, chat_id, message_id, timeout=15):
    try:
        tg_call(
            token,
            "deleteMessage",
            {"chat_id": chat_id, "message_id": message_id},
            timeout=timeout,
        )
        return True
    except TelegramError as exc:
        log("status delete failed: %s" % exc)
        return False


def clear_status(token, chat_id, state):
    """Remove the live progress message so the finished answer replaces it."""
    message_id = state.get("status_message_id")
    if message_id:
        delete_message(token, chat_id, message_id)
    state["status_message_id"] = None
    state["progress_steps"] = 0
    state["last_progress_at"] = 0
    persist(state)


def describe_tool(tool_name, tool_input, limit=900, collapse=True):
    """A compact, phone-readable description of a tool call.

    `collapse` folds newlines into spaces — right for a one-line progress
    ticker, wrong for a permission preview where a multi-line script should
    stay readable.
    """
    tool_input = tool_input if isinstance(tool_input, dict) else {}
    if tool_name == "Bash":
        detail = tool_input.get("command", "")
    elif tool_name in ("Edit", "Write", "NotebookEdit", "Read"):
        detail = tool_input.get("file_path", "")
    elif tool_name in ("WebFetch", "WebSearch"):
        detail = tool_input.get("url") or tool_input.get("query", "")
    elif tool_name in ("Glob", "Grep"):
        detail = tool_input.get("pattern", "")
    elif tool_name == "Skill":
        detail = tool_input.get("skill", "")
    else:
        try:
            detail = json.dumps(tool_input, ensure_ascii=False)
        except Exception:
            detail = str(tool_input)
    detail = " ".join(str(detail).split()) if collapse else str(detail).strip()
    if len(detail) > limit:
        detail = detail[:limit] + " …"
    return detail


def poll_messages(token, chat_id, offset, poll_seconds, since_ts=0):
    """One long-poll round.

    Returns (new_offset, [texts]) with only plain-text messages from the
    authorized chat. Messages predating `since_ts` are dropped so a stale
    backlog can never be injected as an instruction.
    """
    result = tg_call(
        token,
        "getUpdates",
        {"offset": offset, "timeout": poll_seconds, "allowed_updates": ["message"]},
        timeout=poll_seconds + 15,
    )
    texts = []
    new_offset = offset
    for update in result or []:
        new_offset = max(new_offset, int(update.get("update_id", 0)) + 1)
        message = update.get("message") or {}
        text = (message.get("text") or "").strip()
        if not text:
            continue
        incoming_chat = str((message.get("chat") or {}).get("id", ""))
        if incoming_chat != str(chat_id):
            log("ignored message from unauthorized chat %s" % incoming_chat)
            continue
        if since_ts and int(message.get("date", 0)) < int(since_ts) - 5:
            log("ignored stale message (date %s)" % message.get("date"))
            continue
        texts.append(text)
    return new_offset, texts


def drain(token, chat_id, offset=0):
    """Consume any pending backlog and return the next offset."""
    try:
        new_offset, _ = poll_messages(token, chat_id, offset, 0)
        return new_offset
    except TelegramError as exc:
        log("drain failed: %s" % exc)
        return offset


def wait_for_reply(token, chat_id, state, deadline, poll_seconds=None):
    """Long-poll until a message arrives or `deadline` passes.

    Returns (text, new_offset) — text is None on timeout. The offset is
    persisted after every round so a crash cannot replay old messages.
    """
    offset = int(state.get("offset", 0))
    since_ts = int(state.get("started_at", 0))
    window = poll_seconds or DEFAULTS["poll_seconds"]
    while time.time() < deadline:
        remaining = int(deadline - time.time())
        this_poll = max(1, min(window, remaining))
        try:
            offset, texts = poll_messages(token, chat_id, offset, this_poll, since_ts)
        except TelegramError as exc:
            log("poll failed: %s" % exc)
            time.sleep(5)
            continue
        if offset != state.get("offset"):
            state["offset"] = offset
            persist(state)
        if texts:
            return texts[0] if len(texts) == 1 else "\n".join(texts), offset
    return None, offset


def emit(payload):
    """Write hook JSON to stdout and exit 0."""
    sys.stdout.write(json.dumps(payload, ensure_ascii=False))
    sys.stdout.flush()
    sys.exit(0)
