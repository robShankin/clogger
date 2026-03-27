---
name: clogger
description: Manage Codex session logging. Use when the user explicitly runs /clogger, /clogger start, /clogger resume, /clogger stop, or /clogger status.
argument-hint: [start|resume|stop|status]
disable-model-invocation: true
allowed-tools: Bash
---

Manage clogger by shelling out to the installed helper in the current working directory.

All paths use `$PWD` because the helper writes log state into the user's current project.

---

## If $ARGUMENTS is empty or `start`

Run:

```bash
~/.claude/cloggerctl start
```

Reply with exactly the command stdout.

If the Bash call fails because the helper is missing, reply with exactly:

`clogger is not installed - run ./install.sh`

---

## If $ARGUMENTS is `resume`

Run:

```bash
~/.claude/cloggerctl resume
```

Reply with exactly the command stdout.

If the Bash call fails because the helper is missing, reply with exactly:

`clogger is not installed - run ./install.sh`

---

## If $ARGUMENTS is `stop`

Run:

```bash
~/.claude/cloggerctl stop
```

Reply with exactly the command stdout.

If the Bash call fails because the helper is missing, reply with exactly:

`clogger is not installed - run ./install.sh`

---

## If $ARGUMENTS is `status`

Run:

```bash
~/.claude/cloggerctl status
```

Reply with exactly the command stdout.

If the Bash call fails because the helper is missing, reply with exactly:

`clogger is not installed - run ./install.sh`
