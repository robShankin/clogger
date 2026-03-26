#!/usr/bin/env bash
# Install clogger skill to ~/.claude/skills/

set -euo pipefail

SKILL_DIR="$HOME/.claude/skills"
SKILL_DIR_SRC="$(dirname "$0")/skills"

mkdir -p "$SKILL_DIR"
cp "$SKILL_DIR_SRC/clogger.md" "$SKILL_DIR/clogger.md"
cp "$SKILL_DIR_SRC/clogger-stop.md" "$SKILL_DIR/clogger-stop.md"
cp "$SKILL_DIR_SRC/clogger-status.md" "$SKILL_DIR/clogger-status.md"

echo "clogger installed. Use /clogger to start, /clogger-stop to stop, /clogger-status to check."
