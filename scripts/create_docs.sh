#!/usr/bin/env bash
set -euo pipefail

# Create directory structure
mkdir -p docs/{overview,architecture,guides,adapters,databases,exporters,ui,ops,meta}

# Helper: write a file only if it doesn't already exist
write_if_missing() {
  local path="$1"
  shift
  if [[ -f "$path" ]]; then
    echo "skip $path"
  else
    mkdir -p "$(dirname "$path")"
    cat > "$path" <<'EOF'
$CONTENT
EOF
    # Replace placeholder with actual content passed as $2 (a here-doc can't take args directly)
  fi
}

# Because here-doc with function args is messy, use explicit heredocs per file

# ========== docs/index.md ==========
cat > docs/index.md <<'EOF'
# Profilis

A high‑performance, non‑blocking profiler for Python web apps.

- **Frameworks**: Flask, FastAPI, Sanic
- **Databases**: SQLAlchemy, pyodbc, MongoDB, Neo4j
- **UI**: Built‑in, minified dashboard
- **Exporters**: JSONL (rotating), Prometheus, OTLP (future)

## Quick start (Flask)
```bash
pip install profilis[flask,sqlalchemy]
```
```python
from flask import Flask
from profilis.integrations.flask_ext import ProfilisFlask
app = Flask(__name__)
sg = ProfilisFlask(app, ui_enabled=True, ui_prefix="/_profilis")
@app.get('/health')
def ok(): return {'ok': True}
# Visit /_profilis for the dashboard
```
EOF

# ========== overview/problem-statement.md ==========
cat > docs/overview/problem-statement.md <<'EOF'
# Problem statement

APIs in modern (GenAI) stacks get slow without clear visibility. Tooling is fragmented or heavy.
Profilis provides a **drop‑in, production‑safe** profiler with **microsecond‑level overhead**.
EOF

# ========== overview/roadmap.md ==========
cat > docs/overview/roadmap.md <<'EOF'
# Roadmap

See GitHub Project: *Profilis – v0 Roadmap*.

- v0.1.0 — Core + Flask + SQLAlchemy + UI
- v0.2.0 — pyodbc + Mongo + Neo4j
- v0.3.0 — ASGI (FastAPI/Sanic)
- v0.4.0 — Sampling + Prometheus + Resilience
- v1.0.0 — Benchmarks + Docs + Release
EOF

# ========== architecture/architecture.md ==========
cat > docs/architecture/architecture.md <<'EOF'
# Architecture

```mermaid
flowchart LR
  subgraph App
    FW[Framework adapters]
    DEC[Decorators]
    DBI[DB adapters]
  end
  subgraph Core
    CTX[ContextVars]
    EMT[Emitter]
    Q[Async Collector]
    ST[StatsStore]
  end
  subgraph Exporters
    JSONL[JSONL]
    PROM[Prometheus]
    OTLP[(OTLP)]
  end
  subgraph UI
    API[/metrics.json/]
    HTML[Dashboard]
  end
  FW --> EMT
  DEC --> EMT
  DBI --> EMT
  EMT --> ST
  EMT --> Q
  Q --> JSONL
  Q --> PROM
  Q --> OTLP
  ST --> API --> HTML
```
EOF

# ========== architecture/deployment.md ==========
cat > docs/architecture/deployment.md <<'EOF'
# Deployment

- Per‑process queue + writer thread (no cross‑process locks).
- Prometheus scrapes per‑worker /metrics.
- JSONL rotates; ship with fluent‑bit/vector.

Graceful shutdown: keep serving until in‑flight requests finish, then **best‑effort flush with timeout**.
EOF

# ========== architecture/data-model.md ==========
cat > docs/architecture/data-model.md <<'EOF'
# Data model

**Request**
- ts_ms, trace_id, span_id, method, route, status, latency_ms, bytes_in/out, exception, exception_type

**Function**
- trace_id, span_id, parent_span_id, name, latency_ms, success, exception_type

**DB**
- trace_id, span_id, parent_span_id, db_vendor, statement (redacted), duration_ms, rowcount, extra
EOF

# ========== guides/getting-started.md ==========
cat > docs/guides/getting-started.md <<'EOF'
# Getting started

```bash
pip install profilis[flask,sqlalchemy]
```

See also: adapters/ and databases/ guides for framework/DB specifics.
EOF

# ========== guides/configuration.md ==========
cat > docs/guides/configuration.md <<'EOF'
# Configuration

Key options:
- `enabled` (bool)
- `sample_rate` (0.0..1.0)
- `route_exclude` (list/prefix/regex)
- `non_blocking` (default: true)
- `queue_size`, `flush_interval_s`, `batch_max`
- `exporter` (jsonl|prometheus|otlp)
- `jsonl_path`, rotation size/time
- `ui_enabled`, `ui_prefix`, `ui_auth_token`
EOF

# ========== guides/sampling.md ==========
cat > docs/guides/sampling.md <<'EOF'
# Sampling

- Global `sample_rate`
- Per‑route overrides
- Always sample errors (5xx)
- Deterministic tests: seed RNG
EOF

# ========== guides/reliability.md ==========
cat > docs/guides/reliability.md <<'EOF'
# Reliability

- Bounded queue with drop‑oldest
- Exporter failures: noop mode + warn once
- Graceful shutdown: flush with timeout
- Health metrics: events dropped, queue depth
EOF

# ========== guides/performance.md ==========
cat > docs/guides/performance.md <<'EOF'
# Performance

- Hot path: ~10–20µs per event
- Use `perf` extra (`orjson`)
- Tuning: queue_size, batch_max, flush_interval
- Prefer Prometheus aggregates in high‑QPS paths
EOF

# ========== guides/troubleshooting.md ==========
cat > docs/guides/troubleshooting.md <<'EOF'
# Troubleshooting

- UI shows no data → sampling 0? route excluded?
- Disk full → JSONL exporter disabled (warn once)
- High CPU → reduce statement preview length; lower sample rate; disable full SQL capture.
EOF

# ========== adapters/flask.md ==========
cat > docs/adapters/flask.md <<'EOF'
# Flask

```python
from profilis.integrations.flask_ext import ProfilisFlask
sg = ProfilisFlask(app, ui_enabled=True, ui_prefix="/_profilis")
```
EOF

# ========== adapters/fastapi.md ==========
cat > docs/adapters/fastapi.md <<'EOF'
# FastAPI

```python
from profilis.integrations.asgi_middleware import ProfilisASGIMiddleware
app.add_middleware(ProfilisASGIMiddleware, cfg=cfg)
```
EOF

# ========== adapters/sanic.md ==========
cat > docs/adapters/sanic.md <<'EOF'
# Sanic

Use native middleware or mount ASGI UI.
EOF

# ========== adapters/functions.md ==========
cat > docs/adapters/functions.md <<'EOF'
# @profile_function

```python
from profilis.core.decorators import profile_function

@profile_function()
def work(): ...
```
EOF

# ========== databases/sqlalchemy.md ==========
cat > docs/databases/sqlalchemy.md <<'EOF'
# SQLAlchemy

Hook before/after cursor execute; supports async via `.sync_engine`.
Redaction on by default.
EOF

# ========== databases/pyodbc.md ==========
cat > docs/databases/pyodbc.md <<'EOF'
# pyodbc

Wrap `cursor.execute|executemany`. Configure `db_vendor='mssql'`.
EOF

# ========== databases/mongodb.md ==========
cat > docs/databases/mongodb.md <<'EOF'
# MongoDB

PyMongo CommandListener; Motor supported. Preview: `<cmd> db.collection`.
EOF

# ========== databases/neo4j.md ==========
cat > docs/databases/neo4j.md <<'EOF'
# Neo4j

Wrap `Session.run` / `AsyncSession.run`; counters from `summary`.
EOF

# ========== exporters/jsonl.md ==========
cat > docs/exporters/jsonl.md <<'EOF'
# JSONL exporter

- Rotation by size/time
- Atomic rename
- Example path: `logs/profilis.jsonl`
EOF

# ========== exporters/prometheus.md ==========
cat > docs/exporters/prometheus.md <<'EOF'
# Prometheus exporter

Metrics:
- `profilis_http_requests_total`
- `profilis_http_request_duration_seconds` (histogram)
- `profilis_db_queries_total`
- `profilis_db_query_duration_seconds` (histogram)
- `profilis_function_calls_total`
- `profilis_function_duration_seconds`

Label plan: service, instance, worker, route/status, function, db_vendor.
EOF

# ========== exporters/otlp.md ==========
cat > docs/exporters/otlp.md <<'EOF'
# OTLP (future)
Export spans to Tempo/Jaeger via OTLP.
EOF

# ========== ui/ui.md ==========
cat > docs/ui/ui.md <<'EOF'
# Built‑in UI

- Served via Flask blueprint or ASGI app
- `/metrics.json` → StatsStore snapshot
- Bearer token support
EOF

# ========== ops/benchmarks.md ==========
cat > docs/ops/benchmarks.md <<'EOF'
# Benchmarks

Use `pytest-benchmark` + `hey/wrk`. Track p50/p95 deltas.
EOF

# ========== ops/release.md ==========
cat > docs/ops/release.md <<'EOF'
# Release checklist

- Bump version (SemVer)
- Tag `vX.Y.Z`
- Build wheels & sdist; TestPyPI → PyPI
- GitHub Release notes; update CHANGELOG
EOF

# ========== ops/security-privacy.md ==========
cat > docs/ops/security-privacy.md <<'EOF'
# Security & privacy

- Redaction ON by default (strings/numerics → ?)
- Limit statement preview length
- Avoid PII in logs; document opt‑in full capture
EOF

# ========== meta/contributing.md ==========
cat > docs/meta/contributing.md <<'EOF'
# Contributing

See CONTRIBUTING.md in repo root. Summary:
- Branch: trunk‑based (`feat/*`, `fix/*`)
- Conventional Commits
- `ruff`, `mypy`, `pytest` must pass
EOF

# ========== meta/development-guidelines.md ==========
cat > docs/meta/development-guidelines.md <<'EOF'
# Development guidelines

- Trunk‑based; squash merges
- Small PRs; tests + docs required
- Code style: ruff + black; mypy strict
- Perf‑sensitive changes include benchmarks
EOF

# ========== meta/code-of-conduct.md ==========
cat > docs/meta/code-of-conduct.md <<'EOF'
# Code of Conduct

Be respectful. Harassment or discrimination is not tolerated.
EOF

echo "[ok] docs/ scaffolded"
