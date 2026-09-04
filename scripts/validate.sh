#!/usr/bin/env bash
# Check that this folder is a complete Agent Plugin.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FAIL=0

need() {
  if [[ ! -e "$1" ]]; then
    echo "missing $1" >&2
    FAIL=1
  fi
}

need "$ROOT/plugin.json"
need "$ROOT/.cursor-plugin/plugin.json"
need "$ROOT/.claude-plugin/plugin.json"
need "$ROOT/AGENTS.md"
need "$ROOT/WORKSPACE.md"

python3 - <<PY
import json, sys
from pathlib import Path
root = Path("$ROOT")
plugin = json.loads((root / "plugin.json").read_text())
assert plugin.get("\$schema", "").endswith("plugin.schema.json"), plugin.get("\$schema")
assert plugin.get("name") == "landing-pages", plugin.get("name")
names = ["client-funnel-pages", "funnel-qc", "deploy-ghl"]
for name in names:
    skill = root / "skills" / name / "SKILL.md"
    if not skill.is_file():
        print(f"missing {skill}", file=sys.stderr)
        sys.exit(1)
    text = skill.read_text()
    if not text.startswith("---"):
        print(f"{skill} has no frontmatter", file=sys.stderr)
        sys.exit(1)
    if f"name: {name}" not in text.split("---", 2)[1]:
        print(f"{skill} name does not match folder", file=sys.stderr)
        sys.exit(1)
print("plugin.json and three skills look valid")
PY

if [[ "$FAIL" -ne 0 ]]; then
  exit 1
fi
