# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## Project: clogger (Codex Logger)

A lightweight, reusable mechanism to automatically log every user message and Codex response — with timestamps — to a text file in the current working directory. Designed to be shareable and togglable across any Codex session.

## Design Goals

- **Lightweight**: minimal token overhead, no complex logic
- **Low latency**: log writes must be non-blocking or near-instant
- **Portable**: works in any project directory, ideally as a shareable skill
- **Passive**: logs without user intervention once enabled

## Implementation Approach: Hook-Based

The active implementation uses hooks plus transcript parsing instead of asking Codex to log its own replies.

- Hook config is currently installed through `~/.claude/settings.json`
- Transcript discovery checks `~/.codex/sessions`, `~/.Codex/sessions`, and `~/.claude/projects`
- `/clogger` only manages session state; hooks do the actual logging

### Relevant hook types
- `UserPromptSubmit` — fires when the user submits a message; receives the prompt text via stdin as JSON
- `Stop` — fires when Codex finishes a turn; receives session metadata

### Log file
- Filename: `clogger_<YYYY-MM-DD>_<suffix>.txt` under `clogger-files/` in the cwd
- Format:
  ```
  [2026-03-26T14:32:00Z] USER: <message text or [file: filename.ext]>
  [2026-03-26T14:32:05Z] CODEX: <response text>
  ---
  ```

### Current design notes
1. `UserPromptSubmit` stores the pending prompt in a per-session state file under `clogger-files/.clogger-sessions/`.
2. `Stop` reads the transcript and prefers `task_complete.last_agent_message` for the final assistant text.
3. Dedupe is mandatory because `Stop` can fire more than once for the same completed turn.
4. The state is session-scoped, so multiple sessions in one project can log independently.

## Skill File Approach

The skill is now only a control surface for `start`, `resume`, `stop`, and `status`. It shells out to the installed helper and does not perform any per-turn log appends itself.

## Key Files

- `clogger.py` — helper CLI and hook handlers
- `skills/clogger/SKILL.md` — `/clogger` control surface
- `install.sh` — installs the skill, helper, wrapper, permissions, and hooks
- `uninstall.sh` — removes the helper, skill, wrapper, permissions, and hooks

## README

After any material changes to skills, commands, or user-facing behavior, update `README.md` to reflect them — without being asked.

## Pressure Test Notes

- `Stop` should retry briefly because transcript writes can lag the hook event.
- Keep transcript parsing bounded to the tail of the file.
- Preserve log append mode and do not truncate existing files.
- Do not reintroduce any design that depends on the model remembering to self-log.
