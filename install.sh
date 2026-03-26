#!/usr/bin/env bash
# Install clogger skill to ~/.claude/skills/

set -euo pipefail

SKILL_DIR="$HOME/.claude/skills"
SKILL_DIR_SRC="$(dirname "$0")/skills"
SETTINGS="$HOME/.claude/settings.json"

mkdir -p "$SKILL_DIR"
rm -rf "$SKILL_DIR/clogger"
cp -r "$SKILL_DIR_SRC/clogger" "$SKILL_DIR/clogger"

# Install append helper script (avoids shell-redirection permission matching issues)
APPEND_SCRIPT="$HOME/.claude/clogger-append"
cat > "$APPEND_SCRIPT" << 'SCRIPTEOF'
#!/usr/bin/env bash
# clogger-append <logfile> — reads stdin, prepends ISO8601 timestamp to USER: and CLAUDE: lines
TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
while IFS= read -r line; do
  if [[ "$line" == "USER: "* ]] || [[ "$line" == "CLAUDE: "* ]]; then
    printf '[%s] %s\n' "$TS" "$line"
  else
    printf '%s\n' "$line"
  fi
done >> "$1"
SCRIPTEOF
chmod +x "$APPEND_SCRIPT"

# Add required bash permissions to settings.json so clogger never prompts for permission
CLOGGER_PERMS=(
  "Bash(mkdir -p:*)"
  "Bash(printf:*)"
  "Bash($APPEND_SCRIPT:*)"
)

if command -v python3 &>/dev/null; then
  python3 - "$SETTINGS" "${CLOGGER_PERMS[@]}" << 'PYEOF'
import sys, json, os

settings_path = sys.argv[1]
new_perms = sys.argv[2:]

if os.path.exists(settings_path):
  with open(settings_path) as f:
    settings = json.load(f)
else:
  settings = {}

perms = settings.setdefault("permissions", {})
allow = perms.setdefault("allow", [])

added = 0
for p in new_perms:
  if p not in allow:
    allow.append(p)
    added += 1

with open(settings_path, "w") as f:
  json.dump(settings, f, indent=2)
  f.write("\n")

print(f"clogger: added {added} permission rule(s) to {settings_path}")
PYEOF
else
  echo "Warning: python3 not found — skipping settings.json update. Add these permission rules manually:"
  for p in "${CLOGGER_PERMS[@]}"; do
    echo "  $p"
  done
fi

echo "clogger installed. Use /clogger to start, /clogger stop to stop, /clogger status to check."
