#!/usr/bin/env bash
# Repo State Checker — checks ONLY registered repos on local + Pro
# Uses $HOME paths for portability across machines
set -euo pipefail

REGISTRY="${1:-$HOME/projects/todo-exec/config/repo_registry.env}"
if [[ ! -f "$REGISTRY" ]]; then
  echo "MISSING REGISTRY: $REGISTRY" >&2
  exit 2
fi
# shellcheck disable=SC1090
source "$REGISTRY"

repo_state() {
  local dir="$1"
  echo "== $(basename "$dir") =="

  if [[ ! -d "$dir" ]]; then
    echo "MISSING_DIR $dir"
    echo
    return
  fi

  cd "$dir"
  if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "NOT_GIT_REPO $dir"
    echo
    return
  fi

  local br head dirty upstream ab
  br="$(git rev-parse --abbrev-ref HEAD)"
  head="$(git rev-parse --short HEAD)"
  dirty="$(git status --porcelain | wc -l | tr -d ' ')"
  echo "branch=$br head=$head dirty_files=$dirty"
  git log -1 --oneline || true

  git fetch -q --prune 2>/dev/null || true
  upstream="$(git rev-parse --abbrev-ref --symbolic-full-name @{u} 2>/dev/null || true)"
  if [[ -n "$upstream" ]]; then
    ab="$(git rev-list --left-right --count "$upstream"...HEAD 2>/dev/null || true)"
    echo "upstream=$upstream ahead/behind=$ab"
  else
    echo "upstream=NONE"
  fi
  echo
}

echo "=== LOCAL ($(hostname)) ==="
repo_state "$BRAIN_REPO"
repo_state "$TOOLING_REPO"

if [[ -n "${PRO_HOST:-}" ]]; then
  echo "=== PRO ==="
  # Use portable $HOME path, not hardcoded /Users/...
  ssh -o ConnectTimeout=3 "$PRO_HOST" 'bash -l -c '\''
    set -euo pipefail
    REGISTRY="$HOME/projects/todo-exec/config/repo_registry.env"
    if [[ ! -f "$REGISTRY" ]]; then
      echo "MISSING REGISTRY ON PRO: $REGISTRY"
      exit 2
    fi
    source "$REGISTRY"

    repo_state() {
      local dir="$1"
      echo "== $(basename "$dir") =="
      if [[ ! -d "$dir" ]]; then echo "MISSING_DIR $dir"; echo; return; fi
      cd "$dir"
      if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then echo "NOT_GIT_REPO $dir"; echo; return; fi
      br=$(git rev-parse --abbrev-ref HEAD)
      head=$(git rev-parse --short HEAD)
      dirty=$(git status --porcelain | wc -l | tr -d " ")
      echo "branch=$br head=$head dirty_files=$dirty"
      git log -1 --oneline || true
      git fetch -q --prune 2>/dev/null || true
      upstream=$(git rev-parse --abbrev-ref --symbolic-full-name @{u} 2>/dev/null || true)
      if [[ -n "$upstream" ]]; then
        ab=$(git rev-list --left-right --count "$upstream"...HEAD 2>/dev/null || true)
        echo "upstream=$upstream ahead/behind=$ab"
      else
        echo "upstream=NONE"
      fi
      echo
    }

    repo_state "$BRAIN_REPO"
    repo_state "$TOOLING_REPO"
  '\'''
fi

echo "=== HEAD COMPARISON ==="
LOCAL_BRAIN="$(cd "$BRAIN_REPO" && git rev-parse --short HEAD)"
LOCAL_TOOL="$(cd "$TOOLING_REPO" && git rev-parse --short HEAD)"
if [[ -n "${PRO_HOST:-}" ]]; then
  PRO_HEADS=$(ssh -o ConnectTimeout=3 "$PRO_HOST" 'bash -l -c '\''
    echo "$(cd $HOME/projects/todo-exec && git rev-parse --short HEAD) $(cd $HOME/projects/eval-ops-platform && git rev-parse --short HEAD)"
  '\''' 2>/dev/null || echo "unreachable unreachable")
  PRO_BRAIN=$(echo "$PRO_HEADS" | awk '{print $1}')
  PRO_TOOL=$(echo "$PRO_HEADS" | awk '{print $2}')
  echo "todo-exec:        local=$LOCAL_BRAIN pro=$PRO_BRAIN $([ "$LOCAL_BRAIN" = "$PRO_BRAIN" ] && echo "✓" || echo "⚠ DIVERGED")"
  echo "eval-ops-platform: local=$LOCAL_TOOL  pro=$PRO_TOOL  $([ "$LOCAL_TOOL" = "$PRO_TOOL" ] && echo "✓" || echo "⚠ DIVERGED")"
else
  echo "todo-exec:        local=$LOCAL_BRAIN"
  echo "eval-ops-platform: local=$LOCAL_TOOL"
fi
