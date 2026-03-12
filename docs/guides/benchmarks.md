## Benchmarks

Profilis includes a reproducible benchmark harness under `bench/` with demo apps for **Flask**, **FastAPI**, and **Sanic**.

### Setup

```bash
make venv
```

### Quick benchmarks (on/off)

```bash
make bench-flask
make bench-fastapi
make bench-sanic
make bench-all
```

Results are written to `bench/results/` as JSON.

### Results (table)

`bench/results/` is gitignored by default; curated, checked-in results should go in `bench/results/sample/`.

Latest local results currently in `bench/results/` (quick runs):

| Framework | Tool | Duration | p50 off (ms) | p95 off (ms) | RPS off | p50 on (ms) | p95 on (ms) | RPS on | Events/min (on) | Δp50 (ms) | Δp95 (ms) | ΔRPS |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Flask | py | 20s | 1000.84 | 1004.08 | 45.28 | 1000.97 | 1005.75 | 45.16 | 16984.66 | 0.14 | 1.67 | -0.12 |
| FastAPI | py | 20s | 6.73 | 7.02 | 7419.73 | 7.63 | 7.83 | 6501.38 | 382777.81 | 0.90 | 0.81 | -918.34 |
| Sanic | py | 20s | 5.90 | 16.17 | 748.31 | 6.51 | 17.63 | 684.81 | 41142.29 | 0.61 | 1.47 | -63.50 |

If you want to **publish** numbers in git, copy the JSON results into `bench/results/sample/` and commit only those.

Add JSON results (example):

```bash
cp bench/results/*.json bench/results/sample/
```

Once you have multiple samples (e.g. across machines or tuning knobs), we can extend this section to include an aggregated table (median across runs, etc.).

### Soak (Locust)

```bash
make bench-soak
```

### Tuning

See `bench/TUNING.md` for guidance on `queue_size`, `flush_interval`, and `sample`.
