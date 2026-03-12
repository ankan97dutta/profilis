# Roadmap

See GitHub Project: *Profilis – v0 Roadmap*.

## Version Status

### v0.1.0 — Core + Flask + SQLAlchemy + UI (COMPLETED)
**Released**: September 2025

**Delivered Features:**
- **Core Profiling Engine**
    - AsyncCollector with configurable batching and backpressure handling
    - Emitter for high-performance event creation (≤15µs per event)
    - Runtime context management with trace/span ID support
    - Non-blocking architecture with configurable queue sizes

- **Flask Integration**
    - Automatic request/response profiling with hooks
    - Configurable sampling and route exclusion
    - Exception tracking and error reporting
    - Bytes in/out monitoring (best-effort)

- **SQLAlchemy Instrumentation**
    - Automatic query profiling with microsecond precision
    - Query redaction for security
    - Row count tracking
    - Async engine support

- **Built-in Dashboard**
    - Real-time metrics visualization
    - Error tracking and display
    - Performance trend analysis
    - 15-minute rolling window statistics

- **Exporters**
    - JSONL exporter with automatic rotation
    - Console exporter for development
    - Configurable file retention and naming

- **Function Profiling**
    - @profile_function decorator for sync/async functions
    - Exception tracking and re-raising
    - Nested span support

**Performance Metrics:**
- Event creation: ≤15µs per event
- Memory overhead: ~100 bytes per event
- Throughput: 100K+ events/second
- Latency: Sub-millisecond collection overhead

### v0.2.0 — Additional Database Support (COMPLETED)
**Released**: September 2025

**Delivered Features:**
- **MongoDB Support**
    - PyMongo and Motor integration
    - Command monitoring with comprehensive metrics extraction
    - Query execution time tracking
    - Collection and operation profiling
    - Error tracking and failure analysis

- **Neo4j Integration**
    - Cypher query profiling with session and transaction monitoring
    - Graph traversal metrics and result statistics
    - Both sync and async operation support
    - Query analysis with parameter redaction

- **pyodbc Integration**
    - Raw cursor wrapper for execute/executemany operations
    - SQL monitoring with parameter redaction
    - Multi-vendor database support (SQL Server, PostgreSQL, MySQL, etc.)
    - Non-invasive instrumentation preserving cursor semantics

- **Enhanced Runtime Context**
    - Improved tracing support with parent span ID tracking
    - Better integration with external tracing systems

**Performance Metrics:**
- MongoDB command profiling: ≤15µs overhead
- Neo4j query profiling: ≤15µs overhead
- pyodbc cursor profiling: ≤15µs overhead
- Memory overhead: ~100 bytes per database event
- Throughput: 100K+ database events/second

### v0.3.0 — ASGI Framework Support (COMPLETED)
**Released**: March 2026

**Delivered Features:**
- **ASGI Middleware**
    - Generic `ProfilisASGIMiddleware` for Starlette and any ASGI framework
    - Configurable sampling, route exclusions, and always-sample-errors
    - Route template extraction from scope (e.g. path_format)

- **FastAPI Integration**
    - `instrument_fastapi()` registers ASGI middleware with FastAPI apps
    - Automatic request/response profiling and route detection
    - `make_ui_router()` for built-in dashboard (metrics.json, errors.json, HTML)

- **Sanic Integration**
    - `instrument_sanic_app()` with native request/response/exception middleware
    - `make_ui_blueprint()` for built-in dashboard
    - Optional ASGI app mounting (best-effort by Sanic version)

**Enhancements:**
- Improved async performance and error handling in ASGI/Sanic contexts

### v0.4.0 — Sampling, Prometheus & Resilience (COMPLETED)
**Released**: March 2026

**Delivered Features:**
- **Sampling Policies**
    - Global `sample_rate` (0.0–1.0) for ASGI and Sanic
    - Per-route overrides and route excludes (prefix or regex, e.g. `re:^/static/`)
    - Always sample 5xx responses and exceptions
    - Seedable RNG / custom `rng` for deterministic tests

- **Prometheus Exporter**
    - HTTP: `profilis_http_requests_total`, `profilis_http_request_duration_seconds` (histogram)
    - Functions: `profilis_function_calls_total`, `profilis_function_duration_seconds` (histogram)
    - DB: `profilis_db_queries_total`, `profilis_db_query_duration_seconds` (histogram)
    - Labels: service, instance, worker, route, status, function, db_vendor
    - `/metrics` endpoint for Flask (`make_metrics_blueprint`) and ASGI (`make_asgi_app`)
    - Configurable histogram buckets

- **Reliability**
    - Graceful shutdown: best-effort flush with timeout; never block exit
    - JSONL exporter: disk-full fallback (no-op writer + warn once)
    - Health metrics: `profilis_events_dropped_total`, `profilis_queue_depth` via `register_collector_health_metrics()`

### v1.0.0 — Production Ready (COMPLETED)
**Target**: March 2026

**Planned Features:**
- **Comprehensive Benchmarks**
    - Performance regression testing
    - Load testing scenarios
    - Comparison with alternatives

- **Production Documentation**
    - Deployment guides
    - Monitoring best practices
    - Troubleshooting guides

**Enhancements:**
- Production validation
- Community feedback integration
- Long-term support commitment


## Contributing to the Roadmap

### How to Contribute
1. **Feature Requests**: Open GitHub issues for new features
2. **Implementation**: Submit pull requests for planned features
3. **Testing**: Help test and validate new functionality
4. **Documentation**: Improve and expand documentation
5. **Feedback**: Share your experience and use cases

### Development Guidelines
- Follow the established code patterns
- Include comprehensive tests
- Update documentation for new features
- Consider backward compatibility
- Focus on performance and reliability

### Community Input
- **GitHub Discussions**: Share ideas and feedback
- **Issue Tracking**: Report bugs and request features
- **Pull Requests**: Contribute code improvements
- **Documentation**: Help improve guides and examples

## Release Schedule

### Release Cadence
- **Minor Releases**: Every 3-4 months
- **Patch Releases**: As needed for bug fixes
- **Major Releases**: Annual (v1.0.0)

### Release Process
1. **Feature Freeze**: 2 weeks before release
2. **Testing Phase**: 1 week of intensive testing
3. **Release Candidate**: 1 week before final release
4. **Production Release**: Tagged and documented

### Support Policy
- **Current Release**: Full support and bug fixes
- **Previous Release**: Security fixes only
- **Older Releases**: Community support only

## Success Metrics

### Technical Metrics
- **Performance**: Maintain ≤15µs event creation overhead
- **Reliability**: 99.9% uptime for profiling systems
- **Scalability**: Support 1M+ events/second
- **Memory**: <1MB overhead per 10K events

### Adoption Metrics
- **Downloads**: Track PyPI download statistics
- **GitHub Stars**: Monitor community interest
- **Issues & PRs**: Measure community engagement
- **Documentation**: Track documentation usage

### Quality Metrics
- **Test Coverage**: Maintain >90% test coverage
- **Performance Regression**: Zero performance regressions
- **Security**: Regular security audits
- **Documentation**: Comprehensive and up-to-date guides
