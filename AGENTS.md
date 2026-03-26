# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## Project: clogger (Codex Logger)

A lightweight, reusable mechanism to automatically log every user message and Codex response — with timestamps — to a text file in the current working directory. Designed to be shareable and togglable across any Codex session.

## Design Goals

- **Lightweight**: minimal token overhead, no complex logic
- **Low latency**: log writes must be non-blocking or near-instant
- **Portable**: works in any project directory, ideally as a shareable skill
- **Passive**: logs without user intervention once enabled

## Implementation Approach: Hook-Based (Preferred)

The primary implementation uses Codex's **hooks system** (`~/.Codex/settings.json`) rather than prompting Codex to log — this avoids per-turn token cost.

### Relevant hook types
- `UserPromptSubmit` — fires when the user submits a message; receives the prompt text via stdin as JSON
- `Stop` — fires when Codex finishes a turn; receives session metadata

### Log file
- Filename: `clogger_<YYYY-MM-DD>.txt` in the cwd (or a configurable path)
- Format:
  ```
  [2026-03-26T14:32:00Z] USER: <message text or [file: filename.ext]>
  [2026-03-26T14:32:05Z] Codex: <response text>
  ---
  ```

### Known limitations to design around
1. **Capturing Codex's response text in hooks** is the hard problem. The `Stop` hook does not directly provide the response body — the session transcript file (`.Codex/` project dir) is the most reliable source.
2. **File upload representation**: hooks receive the prompt JSON which may include file metadata; extract filenames to represent as `[file: foo.pdf]`.
3. A skill-only approach (instructing Codex to self-log) does work but costs tokens every turn.

## Skill File Approach (Alternative / Complement)

A `.Codex/skills/clogger.md` file can instruct Codex to append to a log file after each exchange using the `Write` or `Bash` tool. This is simpler to share but adds 1-2 tool calls per turn.

## Key Files

- `skills/clogger.md` — activates logging (`/clogger`)
- `skills/clogger-stop.md` — deactivates logging (`/clogger-stop`)
- `skills/clogger-status.md` — reports current state (`/clogger-status`)
- `install.sh` — copies all skills to `~/.Codex/skills/`
- `uninstall.sh` — removes all skills from `~/.Codex/skills/`

## README

After any material changes to skills, commands, or user-facing behavior, update `README.md` to reflect them — without being asked.

## Pressure Test Notes

- Hook scripts must be fast (<200ms) or they will visibly delay the session
- Log file should be opened in append mode; concurrent session safety is a nice-to-have
- The `Stop` hook approach for capturing Codex's response needs validation — may need to read from the Codex session transcript instead
- Sharing: a skill file is trivially shareable (single markdown file); hook-based requires an install step to modify `settings.json`
