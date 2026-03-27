---
name: clogger
description: Manage Claude session logging. Use when the user explicitly runs /clogger, /clogger start, /clogger resume, /clogger stop, or /clogger status.
argument-hint: [start|resume|stop|status]
disable-model-invocation: true
allowed-tools: Bash, Read, Write
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
   Set TMP_ENTRY = `/tmp/clogger-entry-<SESSION_ID>.txt`
4. Write sentinel — **required, do not skip**: `printf '%s\n' "$PWD/clogger-files/clogger_<SESSION_ID>.txt" > "$PWD/clogger-files/.active-current"`
5. Log this activation exchange: use the Write tool to write the following to TMP_ENTRY, then run `~/.claude/clogger-append "$CLOG_FILE" "$TMP_ENTRY"`:
   ```
   USER: /clogger
   CLAUDE: <your one-line reply>
   ---
   ```

**Permissions check:** Read `~/.claude/settings.json` and, if it exists, `.claude/settings.local.json` in the current working directory. Search the `permissions.allow` arrays in both files for ALL of the following:
- an entry containing `clogger-append`
- an entry containing `Write(/tmp/clogger-entry`

If any are missing from both files combined, append a second line to the reply.

Reply format:
- Permissions found: `clogger on → <filename>`
- Permissions missing: `clogger on → <filename>` then on the next line: `⚠ run ./install.sh — you will be prompted for permission on every log write`

---

## If $ARGUMENTS is `resume`

Reattach to the most recent previously active log file in this cwd.

Use the Read tool on `$PWD/clogger-files/.active-current`.

**If the file exists and is non-empty:**
- Set CLOG_FILE to the trimmed contents of `.active-current`
- Parse SESSION_ID from the CLOG_FILE filename — it is the `YYYY-MM-DD_xxxxxx` suffix before `.txt` (e.g. `clogger_2026-03-26_r8ip9n.txt` → SESSION_ID is `2026-03-26_r8ip9n`)
- Set TMP_ENTRY = `/tmp/clogger-entry-<SESSION_ID>.txt`
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
- After each response, log in two steps — timestamps are added by the helper:
  1. Use the Write tool to write to TMP_ENTRY:
     ```
     USER: <exact verbatim user message>
     CLAUDE: <full response text>
     ---
     ```
  2. Run: `~/.claude/clogger-append "$CLOG_FILE" "$TMP_ENTRY"`
     (clogger-append reads the file and deletes it.)
- Reproduce USER messages **verbatim and in full** — never summarize or abbreviate
- When a "User answered Claude's questions" interaction occurred during this turn, insert a `SELECTED: <question> → <answer>` line between the two CLAUDE lines. Example:
  ```
  USER: give me another list, pizza toppings
  CLAUDE: [Asked user to choose pizza topping: Pepperoni, Mushrooms, Pineapple, Fresh basil]
  SELECTED: What's your ideal pizza topping? → Pepperoni
  CLAUDE: Pepperoni — a solid choice!...
  ---
  ```
- Append silently — no commentary about logging
- If the cwd is not writable, skip silently
- If the Bash exit code is non-zero, silently run: `printf '[APPEND-FAILED %s] turn skipped\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$CLOG_FILE"` to mark the gap. Do not notify the user.

---

## If $ARGUMENTS is `stop`

1. Truncate sentinel: `printf '' > "$PWD/clogger-files/.active-current"`
2. Stop all log appends for the remainder of this session. Do not make any more Write or Bash logging calls.

Reply with exactly one line: `clogger off`

---

## If $ARGUMENTS is `status`

Use the Read tool on `$PWD/clogger-files/.active-current`.

- If the file is empty or does not exist → reply: `clogger off`
- If the file is non-empty AND CLOG_FILE is set in the current session context → reply: `clogger on → <contents of .active-current>`
- If the file is non-empty AND CLOG_FILE is NOT set (new session, no resume yet) → reply: `clogger paused → <contents of .active-current> (run /clogger resume to reattach)`
