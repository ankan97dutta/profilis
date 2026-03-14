#!/usr/bin/env bash
set -euo pipefail

# Optional: set these if you're not already inside the repo dir
: "${GH_OWNER:=}"
: "${GH_REPO:=}"

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

create_ms() {
  local title="$1"
  local desc="$2"
  if gh api "repos/${GH_OWNER}/${GH_REPO}/milestones" --jq '.[]|.title' 2>/dev/null | grep -Fxq "$title"; then
    echo "[info] Milestone exists: $title"
    return 0
  fi
  gh api "repos/${GH_OWNER}/${GH_REPO}/milestones" \
    -f title="$title" -f state="open" -f description="$desc" >/dev/null
  echo "[ok] Created milestone: $title"
}

# NOTE: Titles use EN–DASH (–). Keep as-is.
create_ms "v2.0.0 – Schema & Event Model"           "Versioned event schema, TypedDict contracts, HTTP unification, canonical Emitter API, migration docs"
create_ms "v2.1.0 – Pipeline & Operability"         "Optional processors, StatsStore sink, backpressure visibility, PROFILIS_* env configuration"
create_ms "v2.2.0 – Exporters Hardening"            "Prometheus route normalization and label allowlists; optional faster serialization (orjson)"
create_ms "v2.3.0 – Ecosystem & UI"                 "Multi-worker deployment guide, OTLP exporter, UI time windows and correlation views"
create_ms "v2.4.0 – Collector Architecture (Future)" "Design doc or spike for external collector process; no commitment to ship"

echo
echo "v2 milestones now present:"
gh api "repos/${GH_OWNER}/${GH_REPO}/milestones" --jq '.[] | select(.title | startswith("v2")) | .title'
