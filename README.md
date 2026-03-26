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

You only need to do this once. It works globally across all your Claude Code sessions. The installer also adds the required bash permissions to `~/.claude/settings.json` so clogger never prompts you for permission.

## Use

In any Claude Code session, type these commands directly into the chat:

| Command | Effect |
|---|---|
| `/clogger` | Start a new log for this session |
| `/clogger resume` | Reattach to the most recent active log in this directory |
| `/clogger stop` | Stop logging this session |
| `/clogger status` | Show current log filename (or `clogger off`) |

A file like `clogger-files/clogger_2026-03-26_a3f2b1.txt` will appear in **whatever directory you have open in Claude Code** and grow as you chat. The `clogger-files/` folder is created automatically if it doesn't exist.

### After a context compaction

If Claude compacts its context mid-session, logging will stop (Claude loses its in-context state). Run `/clogger resume` to continue writing to the same log file, or `/clogger` to start a new one.

## What the log looks like

````
[2026-03-26T14:32:00Z] USER: how do I reverse a string in python
[2026-03-26T14:32:01Z] CLAUDE: You can reverse a string with slicing: `s[::-1]`
---
[2026-03-26T14:32:45Z] USER: what about in javascript? here's what I tried: ```js
s.split().reverse().join()
```
[2026-03-26T14:32:46Z] CLAUDE: Close — you need `''` as the split/join delimiter: `s.split('').reverse().join('')`
---
````

## Multiple sessions

Each `/clogger` start creates its own file (the random suffix at the end). They won't collide. Old log files remain in `clogger-files/` as history.

## Uninstall

```bash
./uninstall.sh
```
