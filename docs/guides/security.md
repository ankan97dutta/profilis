# Security

Profilis is designed to run in production, but it can still expose sensitive information if misconfigured. This guide covers practical defaults.

## Dashboards and endpoints

- **Protect the UI**: The built-in dashboard endpoints can reveal routes, error messages, and stack traces. Enable auth (bearer token) and restrict access at the network layer.
- **Avoid public exposure**: Do not expose `/profilis`, `/_profilis`, or `/metrics` to the public internet.

## Data minimization

- **Sampling**: Prefer a lower sampling rate in production, and consider always-sampling only errors/5xx.
- **Exclude sensitive routes**: Exclude authentication and payment routes if you don’t need them.
- **Log destinations**: Treat JSONL logs as sensitive. Store them with appropriate access controls and retention.

## PII and secrets

- **Don’t attach request bodies**: Profilis focuses on timing/metadata. If you add custom events, do not include payloads, headers, tokens, or user identifiers unless you have a clear policy.
- **Redaction**: If you emit DB statements, redact literals (emails, tokens) and prefer parameterized queries.

## Operational security

- **Rotate logs**: Use rotation (`rotate_bytes`, `rotate_secs`) and bounded retention.
- **Least privilege**: If running in containers, use read-only filesystem where possible and only write to the log directory.
