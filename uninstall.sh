#!/usr/bin/env bash
# Remove clogger skill from ~/.claude/skills/

SKILL_DIR="$HOME/.claude/skills"

if [ -d "$SKILL_DIR/clogger" ]; then
  rm -rf "$SKILL_DIR/clogger"
  rm -f "$HOME/.claude/clogger-append"
  echo "clogger uninstalled."
else
  echo "clogger not installed."
fi
