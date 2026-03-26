Clogger is now active. For the rest of this session, after every response you write, silently append the exchange to a log file in the cwd.

First, generate a session ID by running: `printf '%s_%s\n' "$(date +%Y-%m-%d)" "$(LC_ALL=C tr -dc 'a-z0-9' < /dev/urandom | head -c 6)"` — store this as your CLOG_FILE for the session (e.g. `clogger_2026-03-26_a3f2b1.txt`). Use this same filename for every append in this session.

Append format (one Bash call per turn, at the very end of your response):

```
[<ISO8601 timestamp>] USER: <exact user message; for file uploads use [file: filename.ext]>
[<ISO8601 timestamp>] CLAUDE: <your full response text>
---
```

Rules:
- Use a single `bash` append: `cat >> <CLOG_FILE> << 'CLOGEOF'` ... `CLOGEOF`
- Timestamps: use `date -u +%Y-%m-%dT%H:%M:%SZ` for the Claude timestamp; estimate USER timestamp as the same
- After every response, append silently — no commentary about the logging itself
- If the cwd is not writable, skip silently

Start now: generate the session filename, log this activation turn, then reply to the user with exactly one line:
`clogger on → <filename>`
