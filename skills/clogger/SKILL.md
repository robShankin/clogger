---
name: clogger
description: Manage Claude session logging. Use when the user explicitly runs /clogger, /clogger start, /clogger resume, /clogger stop, or /clogger status.
argument-hint: [start|resume|stop|status]
disable-model-invocation: true
allowed-tools: Bash, Read
---

Manage Claude session logging. Branch on $ARGUMENTS:

All paths use `$PWD` — logs go in the user's current project directory, not the skill directory.

---

## If $ARGUMENTS is empty, `start`

Always create a brand-new log file. Ignore any existing `.active-current` file.

Run these steps **as separate Bash calls in order — do not combine**:

1. `mkdir -p "$PWD/clogger-files"`
2. `printf '%s_%s\n' "$(date +%Y-%m-%d)" "$(LC_ALL=C tr -dc 'a-z0-9' < /dev/urandom | head -c 6)"` — capture output as SESSION_ID
3. Set CLOG_FILE = `$PWD/clogger-files/clogger_<SESSION_ID>.txt`
4. Write sentinel — **required, do not skip**: `printf '%s\n' "$PWD/clogger-files/clogger_<SESSION_ID>.txt" > "$PWD/clogger-files/.active-current"`
5. Log this activation exchange to CLOG_FILE using `~/.claude/clogger-append "$CLOG_FILE" << 'CLOGEOF'` with `USER: /clogger` and `CLAUDE: <your one-line reply>`

**Permissions check:** Read `~/.claude/settings.json` and, if it exists, `.claude/settings.local.json`. Search the `permissions.allow` arrays for any entry containing `clogger-append`. If not found in either file, append a second line to the reply.

Reply format:
- Permissions found: `clogger on → <filename>`
- Permissions missing: `clogger on → <filename>` then on the next line: `⚠ run ./install.sh — you will be prompted for permission on every log write`

---

## If $ARGUMENTS is `resume`

Reattach to the most recent previously active log file in this cwd.

Use the Read tool on `$PWD/clogger-files/.active-current`.

**If the file exists and is non-empty:**
- Set CLOG_FILE to the trimmed contents of `.active-current`
- Resume logging to that file — do not generate a new SESSION_ID or overwrite the sentinel
- Reply with exactly one line: `clogger resumed → <filename>`

**If the file is empty or does not exist:**
- Reply with exactly one line: `no active session to resume — use /clogger to start one`

---

For every subsequent response this session, silently append to CLOG_FILE:

```
[<ISO8601 timestamp>] USER: <exact verbatim user message; file uploads as [file: filename.ext]>
[<ISO8601 timestamp>] CLAUDE: <full response text>
---
```

Rules:
- After each response, append in a single Bash call — no `$()` substitution needed, timestamps are added by the helper:
  ```
  ~/.claude/clogger-append "$CLOG_FILE" << 'CLOGEOF'
  USER: <exact verbatim user message>
  CLAUDE: <full response text>
  ---
  CLOGEOF
  ```
  CLOG_FILE is the absolute path set above.
- Reproduce USER messages **verbatim and in full** — never summarize or abbreviate
- Strip markdown formatting from both USER and CLAUDE text before logging. Specifically: remove `**`/`*`/`_` wrapping (bold/italic), remove backticks, remove `|` from table rows, remove `>` blockquote prefixes. Convert to plain readable text. This prevents shell safety checks from firing on markdown syntax inside the heredoc.
- Append silently — no commentary about logging
- If the cwd is not writable, skip silently
- If the Bash exit code is non-zero, silently run: `printf '[APPEND-FAILED %s] turn skipped\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$CLOG_FILE"` to mark the gap. Do not notify the user.

---

## If $ARGUMENTS is `stop`

1. Truncate sentinel: `printf '' > "$PWD/clogger-files/.active-current"`
2. Stop all log appends for the remainder of this session. Do not make any more Bash logging calls.

Reply with exactly one line: `clogger off`

---

## If $ARGUMENTS is `status`

Use the Read tool on `$PWD/clogger-files/.active-current`.

If the file exists and is non-empty → reply: `clogger on → <contents of .active-current>`
Otherwise → reply: `clogger off`
