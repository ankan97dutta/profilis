# Troubleshooting

## MkDocs build fails on API reference

If `mkdocs build --strict` fails with errors like “could not collect `profilis...`”:

- Ensure the package is importable:

```bash
pip install -e .
mkdocs build --strict
```

- Or ensure `mkdocstrings` is configured with `paths: [src]` in `mkdocs.yml` (this repo does).

## No events / empty dashboard

- Verify your app is instrumented (adapter/middleware installed).
- Verify you created an `AsyncCollector` and that it’s not immediately garbage collected.
- If using sampling, temporarily set it to 1.0 to confirm wiring.

## High memory usage

- Reduce `queue_size` and/or `batch_max`.
- Lower sampling rate.
- Enable `drop_oldest=True` if you prefer bounded memory under load.

## Missing Prometheus metrics

- Confirm you’re scraping the correct path (`/metrics`).
- Ensure you used a `CollectorRegistry()` that matches the exporter and the served endpoint.
