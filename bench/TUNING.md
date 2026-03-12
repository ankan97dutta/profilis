## Tuning Profilis for load tests

### Queue size (`queue_size`)

- **Bigger queue**: fewer drops under bursty load, more memory.
- **Smaller queue**: lower memory, but can drop under sustained load.

Rule of thumb: start at **2048** and increase (4096/8192) if you see `dropped_oldest > 0`.

### Flush interval (`flush_interval`)

- **Lower** (e.g. 0.05–0.1s): lower end-to-end event latency, slightly more wakeups.
- **Higher** (e.g. 0.5–1.0s): fewer wakeups, higher buffering/latency.

For benchmarks (minimize overhead while keeping up), **0.1s** is a reasonable default.

### Sampling (`sample`)

- **1.0**: record every request.
- **0.1**: record ~10% of requests (lower overhead, lower fidelity).

If you’re comparing latency deltas, keep sampling fixed between runs.
