# clogger

Automatically saves everything you say to Claude — and everything Claude says back — to a text file.

## Requirements

- [Claude Code](https://claude.ai/code) installed and working on your machine

## Install (one time, any directory)

```bash
git clone https://github.com/robShankin/clogger.git
cd clogger
./install.sh
```

You only need to do this once. It works globally across all your Claude Code sessions.

## Use

In any Claude Code session, type these commands directly into the chat:

| Command | Effect |
|---|---|
| `/clogger` | Start logging this session |
| `/clogger-stop` | Stop logging this session |
| `/clogger-status` | Show current log filename (or `clogger off`) |

A file like `clogger_2026-03-26_a3f2b1.txt` will appear in **whatever directory you have open in Claude Code** and grow as you chat.

## What the log looks like

```
[2026-03-26T14:32:00Z] USER: how do I reverse a string in python
[2026-03-26T14:32:01Z] CLAUDE: You can reverse a string with slicing: `s[::-1]`
---
[2026-03-26T14:32:45Z] USER: what about in javascript
[2026-03-26T14:32:46Z] CLAUDE: Use `s.split('').reverse().join('')`
---
```

## Multiple sessions same day

Each session gets its own file (the random suffix at the end). They won't collide.

## Uninstall

```bash
./uninstall.sh
```
