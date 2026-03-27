# clogger

Automatically saves everything you say to Codex and everything Codex says back to a text file in the current project.

## What changed

`clogger` now uses hooks plus transcript parsing instead of asking the model to log its own turns.

- `/clogger` only starts, stops, resumes, and reports logging state.
- `UserPromptSubmit` stores the pending user prompt on disk.
- `Elicitation` and `ElicitationResult` capture interactive choice prompts and selections.
- `Stop` reads the session transcript and logs the completed exchange with the final assistant message.
- Session state lives on disk, so coding turns and context compaction no longer depend on model memory.

## Requirements

- Python 3
- A Codex or Claude environment that honors hooks from `~/.claude/settings.json`

## Install

```bash
git clone https://github.com/robShankin/clogger.git
cd clogger
./install.sh
```

The installer:

- copies the `/clogger` skill into `~/.claude/skills/`
- installs the helper at `~/.claude/clogger/clogger.py`
- installs the wrapper at `~/.claude/cloggerctl`
- updates `~/.claude/settings.json` with the needed hook commands and Bash permission

## Use

In a Codex session, type these commands directly into chat:

| Command | Effect |
|---|---|
| `/clogger` | Start a new log file for the current session |
| `/clogger resume` | Attach the current session to the most recent active log file in this directory |
| `/clogger stop` | Stop logging for the current session |
| `/clogger status` | Show whether the current session is logging |

Logs are written under `clogger-files/` in the directory you have open:

- `clogger-files/clogger_<YYYY-MM-DD>_<suffix>.txt`
- `clogger-files/.active-current`
- `clogger-files/.clogger-sessions/<session-id>.json`

## Why this is more reliable

The old design relied on the model remembering to append a log after every reply. That breaks down during long coding turns.

The new design logs from hooks instead:

1. `UserPromptSubmit` stores the newest user message for the session.
2. `Elicitation` and `ElicitationResult` store interactive question/answer state for arrow-key selections and form prompts.
3. `Stop` uses Claude's `last_assistant_message` when available and falls back to transcript parsing when needed.
4. The helper deduplicates completed turns so repeated stop events do not double-log.

This is the key fix for tool-heavy coding sessions.

## What the log looks like

```text
[2026-03-27T00:12:00Z] USER: write a python function that parses csv safely
[2026-03-27T00:12:08Z] CODEX: Here is a safe parser that uses the csv module.
---
```

Multiline prompts and multiline answers are preserved under the labeled first line.

Interactive selections are also preserved:

```text
[2026-03-27T02:37:53Z] USER: show me a real selectable list
[2026-03-27T02:37:58Z] CLAUDE: What would you like to chat about?
[2026-03-27T02:38:00Z] SELECTED: What would you like to chat about? -> Random ideas
[2026-03-27T02:38:03Z] CLAUDE: Nice! Let's brainstorm.
---
```

## Context compaction

Context compaction no longer turns logging off. The session state is stored on disk and the hooks stay active.

`/clogger resume` is only needed when a new session wants to continue writing to the most recent active file.

## Multiple sessions

Each started session gets its own state file and its own log file. Hooks key off the transcript session id, so coding in one session does not overwrite another session's state in the same project.

## Uninstall

```bash
./uninstall.sh
```
