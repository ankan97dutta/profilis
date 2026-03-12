#!/usr/bin/env bash
set -euo pipefail
: "${GH_OWNER:?}"; : "${GH_REPO:?}"

PROJECT_TITLE="${PROJECT_TITLE:-Profilis – v0 Roadmap}"
PROJECT_DESC="${PROJECT_DESC:-High-performance, framework-agnostic profiler with UI and DB adapters.}"

# ---- Parse args: --milestone "..." OR --label "..." ----
MS_FILTER=""
LBL_FILTER=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --milestone) MS_FILTER="$2"; shift 2 ;;
    --label)     LBL_FILTER="$2"; shift 2 ;;
    *) echo "Unknown arg: $1"; exit 2 ;;
  esac
done

if [[ -z "$MS_FILTER" && -z "$LBL_FILTER" ]]; then
  echo "Usage: $0 --milestone \"v0.1.0 – Core + Flask + SQLAlchemy + UI\"  OR  --label \"type:core\""
  exit 2
fi

# ---- Detect owner type ----
OWNER_JSON="$(gh api "users/$GH_OWNER")"
if echo "$OWNER_JSON" | grep -q '"type": "Organization"'; then OWNER_TYPE="org"; else OWNER_TYPE="user"; fi

# ---- Owner ID (for Projects v2) ----
if [ "$OWNER_TYPE" = "org" ]; then
  OWNER_ID="$(gh api graphql -f query='query($login:String!){ organization(login:$login){ id } }' -f login="$GH_OWNER" --jq '.data.organization.id')"
  EXIST_ID="$(gh api graphql -f query='query($login:String!){ organization(login:$login){ projectsV2(first:50){ nodes { id title } } } }' -f login="$GH_OWNER" --jq ".data.organization.projectsV2.nodes[] | select(.title==\"$PROJECT_TITLE\") | .id" || true)"
else
  OWNER_ID="$(gh api graphql -f query='query($login:String!){ user(login:$login){ id } }' -f login="$GH_OWNER" --jq '.data.user.id')"
  EXIST_ID="$(gh api graphql -f query='query($login:String!){ user(login:$login){ projectsV2(first:50){ nodes { id title } } } }' -f login="$GH_OWNER" --jq ".data.user.projectsV2.nodes[] | select(.title==\"$PROJECT_TITLE\") | .id" || true)"
fi

# ---- Create or use project ----
if [ -n "${EXIST_ID:-}" ]; then
  PROJECT_ID="$EXIST_ID"
  echo "[info] Using existing project: $PROJECT_TITLE"
else
  PROJECT_ID="$(gh api graphql -f query='mutation($owner:ID!,$title:String!){ createProjectV2(input:{ownerId:$owner,title:$title}){ projectV2 { id } } }' -f owner="$OWNER_ID" -f title="$PROJECT_TITLE" --jq '.data.createProjectV2.projectV2.id')"
  echo "[ok] Created project: $PROJECT_TITLE"
fi

# ---- Gather issues by milestone or label ----
if [[ -n "$MS_FILTER" ]]; then
  echo "[search] Selecting open issues in milestone: $MS_FILTER"
  ISSUES=$(gh issue list -R "$GH_OWNER/$GH_REPO" --state open --milestone "$MS_FILTER" \
           --json number,id --jq '.[] | [.number, .id] | @tsv')
else
  echo "[search] Selecting open issues with label: $LBL_FILTER"
  ISSUES=$(gh issue list -R "$GH_OWNER/$GH_REPO" --state open --label "$LBL_FILTER" \
           --json number,id --jq '.[] | [.number, .id] | @tsv')
fi

if [ -z "$ISSUES" ]; then
  echo "[warn] No matching open issues found."
  exit 0
fi

# ---- Add each issue to the project ----
while IFS=$'\t' read -r NUM NODE; do
  echo "[add] Adding issue #$NUM to project..."
  gh api graphql -f query='mutation($project:ID!,$content:ID!){ addProjectV2ItemById(input:{projectId:$project, contentId:$content}){ item { id } } }' \
    -f project="$PROJECT_ID" -f content="$NODE" >/dev/null
done <<< "$ISSUES"

echo "[ok] Added issues to project: $PROJECT_TITLE"
