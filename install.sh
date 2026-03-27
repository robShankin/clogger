#!/usr/bin/env bash
# Install clogger skill and hook helpers to ~/.claude/

set -euo pipefail

CLAUDE_HOME="$HOME/.claude"
SKILL_DIR="$CLAUDE_HOME/skills"
SKILL_DIR_SRC="$(dirname "$0")/skills"
INSTALL_DIR="$CLAUDE_HOME/clogger"
WRAPPER_PATH="$CLAUDE_HOME/cloggerctl"
SETTINGS="$CLAUDE_HOME/settings.json"

mkdir -p "$SKILL_DIR"
mkdir -p "$INSTALL_DIR"
rm -rf "$SKILL_DIR/clogger"
cp -r "$SKILL_DIR_SRC/clogger" "$SKILL_DIR/clogger"
cp "$(dirname "$0")/clogger.py" "$INSTALL_DIR/clogger.py"
chmod +x "$INSTALL_DIR/clogger.py"

cat > "$WRAPPER_PATH" <<'SCRIPTEOF'
#!/usr/bin/env bash
set -euo pipefail
exec python3 "$HOME/.claude/clogger/clogger.py" "$@"
SCRIPTEOF
chmod +x "$WRAPPER_PATH"

CLOGGER_PERMS=(
  "Bash(~/.claude/cloggerctl:*)"
  "Bash($HOME/.claude/cloggerctl:*)"
)

if command -v python3 >/dev/null 2>&1; then
  python3 - "$SETTINGS" "${CLOGGER_PERMS[@]}" <<'PYEOF'
import json
import os
import sys

settings_path = sys.argv[1]
new_perms = sys.argv[2:]

if os.path.exists(settings_path):
    with open(settings_path) as handle:
        settings = json.load(handle)
else:
    settings = {}

permissions = settings.setdefault("permissions", {})
allow = permissions.setdefault("allow", [])
for perm in new_perms:
    if perm not in allow:
        allow.append(perm)

hooks = settings.setdefault("hooks", {})

desired_hooks = {
    "UserPromptSubmit": {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "~/.claude/cloggerctl hook-user-prompt-submit",
          }
        ]
    },
    "Elicitation": {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "~/.claude/cloggerctl hook-elicitation",
          }
        ]
    },
    "ElicitationResult": {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "~/.claude/cloggerctl hook-elicitation-result",
          }
        ]
    },
    "Stop": {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "~/.claude/cloggerctl hook-stop",
          }
        ]
    },
}

for event_name, desired_entry in desired_hooks.items():
    entries = hooks.setdefault(event_name, [])
    if not any(entry == desired_entry for entry in entries):
        entries.append(desired_entry)

with open(settings_path, "w") as handle:
    json.dump(settings, handle, indent=2)
    handle.write("\n")

print(f"clogger: updated {settings_path}")
PYEOF
else
  echo "Warning: python3 not found - skipping settings.json update."
  echo "Add these permission rules manually:"
  for perm in "${CLOGGER_PERMS[@]}"; do
    echo "  $perm"
  done
fi

echo "clogger installed. Use /clogger to start, /clogger resume to reattach, /clogger stop to stop, and /clogger status to check."
