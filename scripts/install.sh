#!/usr/bin/env bash
# Link this plugin's skills into a host workspace or Cursor's local plugin dir.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SKILLS="$ROOT/skills"
NAMES=(client-funnel-pages funnel-qc deploy-ghl)

usage() {
  cat <<EOF
Install the landing-pages plugin into a host workspace or Cursor.

Usage:
  ./scripts/install.sh --project DIR [--claude] [--cursor-local]
  ./scripts/install.sh --cursor-local
  ./scripts/install.sh --user-skills

  --project DIR    Symlink the three skills into DIR/.agents/skills
  --claude         Also symlink into DIR/.claude/skills
  --cursor-local   Link this folder to ~/.cursor/plugins/local/landing-pages
  --user-skills    Symlink the three skills into ~/.agents/skills
EOF
}

link_skill() {
  local dest_root="$1"
  mkdir -p "$dest_root"
  local name
  for name in "${NAMES[@]}"; do
    local src="$SKILLS/$name"
    local dest="$dest_root/$name"
    if [[ ! -d "$src" ]]; then
      echo "missing skill: $src" >&2
      exit 1
    fi
    ln -sfn "$src" "$dest"
    echo "linked $dest -> $src"
  done
}

PROJECT=""
DO_CLAUDE=0
DO_CURSOR=0
DO_USER=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --project)
      PROJECT="${2:-}"
      shift 2
      ;;
    --claude)
      DO_CLAUDE=1
      shift
      ;;
    --cursor-local)
      DO_CURSOR=1
      shift
      ;;
    --user-skills)
      DO_USER=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "unknown flag: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ -z "$PROJECT" && "$DO_CURSOR" -eq 0 && "$DO_USER" -eq 0 ]]; then
  usage >&2
  exit 1
fi

if [[ -n "$PROJECT" ]]; then
  link_skill "$PROJECT/.agents/skills"
  if [[ "$DO_CLAUDE" -eq 1 ]]; then
    link_skill "$PROJECT/.claude/skills"
  fi
fi

if [[ "$DO_USER" -eq 1 ]]; then
  link_skill "$HOME/.agents/skills"
fi

if [[ "$DO_CURSOR" -eq 1 ]]; then
  mkdir -p "$HOME/.cursor/plugins/local"
  ln -sfn "$ROOT" "$HOME/.cursor/plugins/local/landing-pages"
  echo "linked $HOME/.cursor/plugins/local/landing-pages -> $ROOT"
fi
