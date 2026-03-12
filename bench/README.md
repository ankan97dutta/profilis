## Benchmarks (Flask/FastAPI/Sanic)

### Setup (repo `.venv`)

```bash
make venv
```

### Quick numbers (writes JSON to `bench/results/`)

```bash
make bench-flask
make bench-fastapi
make bench-sanic
make bench-all
```

- **External tools**: set `TOOL=hey` or `TOOL=wrk` if installed; default is `TOOL=py` (built-in).
- **Tuning knobs**: `QUEUE_SIZE`, `FLUSH_INTERVAL`, `SAMPLE` via `bench/run.py` flags.

### Locust soak (30–60 min)

```bash
make bench-soak
```

## Benchmarks

This folder contains **reproducible load profiles** for Flask/FastAPI/Sanic and scripts to record **p50/p95 deltas** with Profilis enabled vs disabled.

### Prereqs

- **Python**: 3.9+
- **Install (uses repo `.venv`)**:

```bash
make venv
```

- **Load tools** (pick one):
  - **wrk**: `brew install wrk`
  - **hey**: `brew install hey`
  - **built-in**: `TOOL=py` (no external install; used by default)

### Quick benchmark (writes JSON to `bench/results/`)

```bash
make bench-flask
make bench-fastapi
make bench-sanic
make bench-all
```

### Locust soak (30–60 minutes)

```bash
make bench-locust
```

### Output

- **Results**: `bench/results/*.json`
- Each run records:
  - latency p50/p95 (from `wrk`/`hey`)
  - requests/sec
  - **events/min** (from Profilis collector `processed` count)
  - best-effort **CPU%** for the server process (requires `psutil`)
