#!/usr/bin/env bash
# Remove clogger skill, helper scripts, and hook config from ~/.claude/

set -euo pipefail

CLAUDE_HOME="$HOME/.claude"
SKILL_DIR="$CLAUDE_HOME/skills"
INSTALL_DIR="$CLAUDE_HOME/clogger"
WRAPPER_PATH="$CLAUDE_HOME/cloggerctl"
SETTINGS="$CLAUDE_HOME/settings.json"

rm -rf "$SKILL_DIR/clogger"
rm -rf "$INSTALL_DIR"
rm -f "$WRAPPER_PATH"

if command -v python3 >/dev/null 2>&1 && [ -f "$SETTINGS" ]; then
  python3 - "$SETTINGS" <<'PYEOF'
import json
import sys

settings_path = sys.argv[1]

with open(settings_path) as handle:
    settings = json.load(handle)

allow = settings.get("permissions", {}).get("allow", [])
settings.get("permissions", {})["allow"] = [
    perm
    for perm in allow
    if "cloggerctl" not in perm
]

hooks = settings.get("hooks", {})
for event_name in ("UserPromptSubmit", "Elicitation", "ElicitationResult", "Stop"):
    entries = hooks.get(event_name, [])
    filtered = []
    for entry in entries:
        commands = entry.get("hooks", [])
        if any("cloggerctl" in hook.get("command", "") for hook in commands):
            continue
        filtered.append(entry)
    if filtered:
        hooks[event_name] = filtered
    else:
        hooks.pop(event_name, None)

with open(settings_path, "w") as handle:
    json.dump(settings, handle, indent=2)
    handle.write("\n")
PYEOF
fi

echo "clogger uninstalled."
