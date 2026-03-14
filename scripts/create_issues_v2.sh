#!/usr/bin/env bash
set -euo pipefail

# Create v2 roadmap issues. Run after create_milestones_v2.sh.
# Auto-detect GH_OWNER/GH_REPO from git if not set.
if [[ -z "${GH_OWNER:-}" || -z "${GH_REPO:-}" ]]; then
  if [[ -d .git ]]; then
    REMOTE_URL=$(git remote get-url origin)
    if [[ "$REMOTE_URL" =~ github\.com[:/]([^/]+)/([^/]+)\.git ]]; then
      GH_OWNER="${BASH_REMATCH[1]}"
      GH_REPO="${BASH_REMATCH[2]}"
      echo "Auto-detected: GH_OWNER=$GH_OWNER, GH_REPO=$GH_REPO"
    else
      echo "Error: Could not parse GitHub URL from git remote"
      exit 1
    fi
  else
    echo "Error: GH_OWNER and GH_REPO must be set, or run from a git repository"
    exit 1
  fi
fi

issue() {
  local title="$1"; shift
  local body="$1"; shift
  gh issue create -R "$GH_OWNER/$GH_REPO" -t "$title" -b "$body" "$@"
}

# --- v2.0.0 – Schema & Event Model ---
MS_20="v2.0.0 – Schema & Event Model"

issue "v2: Event schema – schema_version and profilis_version" \
"**Stability:** Stable

### Problem in v1
Events are flexible dicts with no formal schema.

### v2 Direction
Introduce versioned schema (\`schema_version\`, \`profilis_version\`).

### Deliverables
- Canonical event definitions and schema documentation
- Add \`schema_version\` (e.g. \`\"2.0\"\`) and optional \`profilis_version\` to every event in \`Emitter._base()\` and adapters
- Document canonical fields per kind in \`docs/\`

### Acceptance
- All emitted events include \`schema_version\`; docs list required/optional fields per kind.
" -m "$MS_20" -l "type:core"

issue "v2: Event model – TypedDict contracts, dict on the wire" \
"**Stability:** Stable

### Problem in v1
Adapters construct payloads manually.

### v2 Direction
Internal \`TypedDict\` contracts while keeping dicts on the wire.

### Deliverables
- \`profilis.core.events\` module with TypedDict (or Protocol) for HTTP, FN, DB
- Type-safe emitter interfaces; use types in processors/exporters only
- Serialization remains dict-based for hot path

### Acceptance
- \`profilis.core.events\` defines HTTPEvent, FNEvent, DBEvent; emitter builds dicts conforming to them.
" -m "$MS_20" -l "type:core"

issue "v2: HTTP event unification – standardize on HTTP kind" \
"**Stability:** Stable

### Problem in v1
Mixed event kinds (\`REQ\`, \`HTTP\`) across adapters.

### v2 Direction
Standardize on \`HTTP\` event structure.

### Deliverables
- Unified event fields: \`kind=\"HTTP\"\`, \`method\`, \`path\`, \`route\`, \`status\`, \`dur_ns\`, \`ts_ns\`, \`trace_id\`, \`span_id\`, \`parent_span_id\`, \`error\`
- Deprecate \`REQ\` / \`REQ_META\` in favor of \`HTTP\` (+ optional meta)
- Update Flask, ASGI, Sanic adapters and Prometheus exporter to use HTTP only

### Acceptance
- All framework adapters emit \`kind=HTTP\` with the same field set; Prometheus treats HTTP only.
" -m "$MS_20" -l "type:core"

issue "v2: Emitter API – canonical emit_http, emit_fn, emit_db" \
"**Stability:** Stable

### Problem in v1
Some adapters bypass emitter and enqueue directly.

### v2 Direction
Provide canonical \`emit_http\`, \`emit_fn\`, \`emit_db\` APIs; avoid direct \`_collector.enqueue\` from adapters.

### Deliverables
- Add \`emit_http(...)\` and \`emit_http_meta(...)\` (or equivalent) on Emitter
- Migrate all framework adapters to use emitter APIs only
- Document that adapters must not call \`_collector.enqueue\` directly

### Acceptance
- No adapter calls \`emitter._collector.enqueue\` for HTTP; all use \`emit_http\` / \`emit_http_meta\`.
" -m "$MS_20" -l "type:core"

issue "v2: Documentation & Migration – v1 to v2 guide" \
"**Stability:** Stable

### Problem in v1
No formal migration guidance.

### v2 Direction
Provide v1 → v2 migration guide.

### Deliverables
- CHANGELOG with breaking changes (event kinds, Emitter API)
- Migration section in README or \`docs/guides/migration-v2.md\`
- Compatibility note for v1 JSONL (read old events or small compat layer in docs)

### Acceptance
- Users can follow the doc to update from v1 to v2; CHANGELOG lists breaking changes.
" -m "$MS_20" -l "type:core"

# --- v2.1.0 – Pipeline & Operability ---
MS_21="v2.1.0 – Pipeline & Operability"

issue "v2: Pipeline architecture – optional processor stage" \
"**Stability:** Experimental

### Problem in v1
Collector pushes batches directly to sinks.

### v2 Direction
Introduce optional processor stage: \`collector → processors → sinks\`.

### Deliverables
- \`AsyncCollector\` accepts optional \`processors: list[Callable[[list[T]], list[T]]]\`
- Flow: dequeue batch → run processors in order → call sink(result)
- Document processor contract (batch in, batch out; no I/O in hot path)
- Example processors: add \`service\`/\`instance\`, route normalization, PII redaction (in \`docs/guides/processors.md\` or examples)

### Acceptance
- Collector can be configured with zero or more processors; default behavior unchanged.
" -m "$MS_21" -l "type:core"

issue "v2: StatsStore integration – built-in StatsStore sink" \
"**Stability:** Stable

### Problem in v1
Users manually wire collectors to StatsStore.

### v2 Direction
Provide built-in StatsStore sink.

### Deliverables
- New \`profilis.core.stats_sink\` (or \`profilis.sinks\`) with a sink callable that updates \`StatsStore\` from batches (e.g. iterate HTTP events, call \`stats.record(dur_ns, error=...)\`)
- Document composition: \`sink = compose(jsonl, stats_sink)\` or prebuilt composite
- Simplify README Quick Start so users don’t write the manual loop

### Acceptance
- One-liner or short snippet to add StatsStore as a sink; README Quick Start uses it.
" -m "$MS_21" -l "type:core"

issue "v2: Backpressure visibility – standardize health metrics" \
"**Stability:** Stable

### Problem in v1
Collector health metrics exist but are not standardized.

### v2 Direction
Export queue depth, dropped events, sink failures consistently.

### Deliverables
- Document queue_depth, dropped_oldest, flush_errors (and any sink-disable behavior)
- Ensure Prometheus \`register_collector_health_metrics\` and/or JSONL/deployment guide expose them
- Deployment guide section on pipeline health

### Acceptance
- Health metrics documented and exportable via Prometheus and/or docs.
" -m "$MS_21" -l "type:core"

issue "v2: Environment configuration – PROFILIS_* variables" \
"**Stability:** Stable

### Problem in v1
Configuration mostly done in code.

### v2 Direction
Introduce environment-based configuration.

### Deliverables
- \`PROFILIS_SAMPLING_RATE\`, \`PROFILIS_ROUTE_EXCLUDES\`, exporter paths, UI bearer token (and other \`PROFILIS_*\` as needed)
- New \`profilis.config\` or extend adapter configs to load from env with code as override
- Document in \`docs/guides/configuration.md\`

### Acceptance
- Key options can be set via env; code overrides env when both are set.
" -m "$MS_21" -l "type:core"

# --- v2.2.0 – Exporters Hardening ---
MS_22="v2.2.0 – Exporters Hardening"

issue "v2: Prometheus exporter hardening – route normalization and label allowlists" \
"**Stability:** Stable

### Problem in v1
Risk of high-cardinality labels.

### v2 Direction
Route normalization and label allowlists.

### Deliverables
- Use templated route as label (not raw path) where possible
- Configurable label allowlist; optional max distinct label values or hashing for high-cardinality routes
- Safe metric labeling strategy documented

### Acceptance
- Prometheus exporter can limit label cardinality; docs describe how to configure.
" -m "$MS_22" -l "type:exporter"

issue "v2: Serialization path – optional faster encoders (e.g. orjson)" \
"**Stability:** Experimental

### Problem in v1
Exporters rely on standard JSON serialization.

### v2 Direction
Add faster serialization paths (e.g. orjson).

### Deliverables
- Benchmark current JSON path; document or add optional faster encoder behind feature flag or \`[perf]\` extra
- No change to default behavior in v2.0

### Acceptance
- Optional orjson path available; default unchanged; benchmarks in \`bench/\`.
" -m "$MS_22" -l "type:exporter" -l "type:perf"

# --- v2.3.0 – Ecosystem & UI ---
MS_23="v2.3.0 – Ecosystem & UI"

issue "v2: Multi-worker deployments – document and optional shared collector" \
"**Stability:** Experimental

### Problem in v1
Each worker runs its own collector.

### v2 Direction
Document worker-local pipelines and optional shared collector mode.

### Deliverables
- Deployment guide: worker-local pipeline as default (one collector per process)
- Optionally document or prototype \"shared collector\" mode (e.g. UDP/socket forwarder to single process) as experimental or future

### Acceptance
- Docs describe recommended multi-worker setup and any experimental shared-collector option.
" -m "$MS_23" -l "type:core"

issue "v2: OpenTelemetry interop – OTLP exporter and context bridge" \
"**Stability:** Experimental

### Problem in v1
Profilis operates outside OTEL ecosystem.

### v2 Direction
Optional OTLP exporter and context bridge.

### Deliverables
- New \`profilis.exporters.otlp\` (or \`profilis.otel\`) behind extra e.g. \`profilis[otel]\`
- Convert Profilis events to OTEL spans/metrics and send via OTLP
- Optional context bridge: read OTEL trace_id/span_id and set Profilis context so IDs align

### Acceptance
- With \`profilis[otel]\`, users can export to an OTLP endpoint and/or align context with OTEL.
" -m "$MS_23" -l "type:exporter"

issue "v2: UI & Analytics – time windows and correlation views" \
"**Stability:** Experimental

### Problem in v1
Limited query capability in current UI.

### v2 Direction
Add time windows and correlation views.

### Deliverables
- Queryable time windows (e.g. last 5/15/60 min)
- Correlation views: e.g. from an error spike show top routes, status codes, slowest functions
- Back by StatsStore or small in-memory event buffer (configurable, bounded)

### Acceptance
- Dashboard supports selectable time range and at least one correlation view (e.g. errors → routes).
" -m "$MS_23" -l "type:ui"

# --- v2.4.0 – Collector Architecture (Future) ---
MS_24="v2.4.0 – Collector Architecture (Future)"

issue "v2: Collector architecture – design doc for external collector process" \
"**Stability:** Future

### Problem in v1
Thread-based collector only.

### v2 Direction
Keep current design; explore external collector process.

### Deliverables
- Architecture spike and design documentation (e.g. sidecar that receives batches)
- No commitment to ship in v2.4; document findings and options in \`docs/architecture/architecture.md\`

### Acceptance
- Design doc or spike document exists; decision on whether to implement is deferred.
" -m "$MS_24" -l "type:core"

echo "Created v2 issues on $GH_OWNER/$GH_REPO"
