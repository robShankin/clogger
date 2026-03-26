#!/usr/bin/env bash
# Remove clogger skill from ~/.claude/skills/

SKILL_DIR="$HOME/.claude/skills"

if [ -f "$SKILL_DIR/clogger.md" ] || [ -f "$SKILL_DIR/clogger-stop.md" ]; then
  rm -f "$SKILL_DIR/clogger.md" "$SKILL_DIR/clogger-stop.md" "$SKILL_DIR/clogger-status.md"
  echo "clogger uninstalled."
else
  echo "clogger not installed."
fi
