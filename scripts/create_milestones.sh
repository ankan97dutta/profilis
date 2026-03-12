#!/usr/bin/env bash
set -euo pipefail

# Optional: set these if you're not already inside the repo dir
: "${GH_OWNER:=}"
: "${GH_REPO:=}"

# If owner/repo not set, try to infer from current git remote
if [[ -z "${GH_OWNER}" || -z "${GH_REPO}" ]]; then
  if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    origin="$(git config --get remote.origin.url || true)"
    if [[ "$origin" =~ github.com[:/](.+)/(.+)\.git ]]; then
      GH_OWNER="${BASH_REMATCH[1]}"
      GH_REPO="${BASH_REMATCH[2]}"
    fi
  fi
fi

if [[ -z "${GH_OWNER}" || -z "${GH_REPO}" ]]; then
  echo "Set GH_OWNER and GH_REPO (e.g., export GH_OWNER=you GH_REPO=profilis), or run inside a cloned repo."
  exit 2
fi

# Helper: create milestone if missing (idempotent)
create_ms() {
  local title="$1"
  local desc="$2"
  # If it already exists, skip
  if gh api "repos/${GH_OWNER}/${GH_REPO}/milestones" --jq '.[]|.title' 2>/dev/null | grep -Fxq "$title"; then
    echo "[info] Milestone exists: $title"
    return 0
  fi
  # Create (open by default)
  gh api "repos/${GH_OWNER}/${GH_REPO}/milestones" \
    -f title="$title" -f state="open" -f description="$desc" >/dev/null
  echo "[ok] Created milestone: $title"
}

# NOTE: The title below uses an EN–DASH (–). Keep it as-is (copy/paste).
create_ms "v0.1.0 – Core + Flask + SQLAlchemy + UI" "Core emitter + Flask + SQLAlchemy + minimal UI"
create_ms "v0.2.0 – pyodbc + Mongo + Neo4j"        "DB adapters for pyodbc, MongoDB, Neo4j"
create_ms "v0.3.0 – ASGI/FastAPI + Sanic"          "ASGI middleware; FastAPI & Sanic adapters"
create_ms "v0.4.0 – Sampling/Prometheus/Resilience" "Sampling policies, Prometheus exporter, reliability"
create_ms "v1.0.0 – Benchmarks + Docs Hardening"   "Benchmarks, docs, release engineering"

# Show result
echo
echo "Milestones now present:"
gh api "repos/${GH_OWNER}/${GH_REPO}/milestones" --jq '.[] | .title'
