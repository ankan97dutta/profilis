## Sample benchmark results

This directory contains **small, curated benchmark outputs** that are safe to commit and reference in docs/PRs.

### What belongs here

- **Representative results**: small files that show the expected output shape and typical numbers.
- **Reproducible runs**: generated from a known command/config so others can rerun and compare.
- **Review-friendly diffs**: outputs that stay relatively stable and are easy to diff in PRs.

### What does not belong here

- **Ad-hoc local runs**: noisy results that change machine-to-machine or run-to-run.
- **Large artifacts**: big JSON/CSV dumps, flamegraphs, profiles, or raw logs.
- **Sensitive data**: anything that might contain PII, secrets, hostnames, or internal endpoints.

### How results are typically generated

Run your benchmark command(s) and write outputs somewhere under `bench/results/`, then copy only the
hand-picked files into `bench/results/sample/`.

If you are using `pytest-benchmark`, one common pattern is:

```bash
pytest bench/ --benchmark-only --benchmark-json bench/results/run.json
cp bench/results/run.json bench/results/sample/
```

### Repo policy

- Only `bench/results/sample/` is intended to be tracked in git.
- Everything else under `bench/results/` is intentionally ignored to avoid committing large/noisy outputs.
