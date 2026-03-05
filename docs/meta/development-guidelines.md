# Development guidelines

- **Trunk‑based**; squash merges
- **Small PRs**; tests + docs required
- **Code style**: ruff + black; mypy strict
- **Perf‑sensitive changes** include benchmarks

## Project setup

### Prerequisites

- **Python**: 3.9 or higher
- **git**: For version control

### One-time setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/ankan97dutta/profilis.git
   cd profilis
   ```

2. **Create and activate a virtual environment**
   ```bash
   python -m venv .venv
   source .venv/bin/activate   # On Windows: .venv\Scripts\activate
   ```

3. **Install the package in editable mode with dev dependencies**
   ```bash
   pip install -e ".[dev]"
   ```
   This installs the library plus pytest, pytest-cov, pytest-asyncio, mypy, ruff, black, pre-commit, and uvicorn.

4. **Install pre-commit hooks** (recommended)
   ```bash
   pre-commit install
   ```
   Hooks run ruff (lint + format), mypy, and basic file checks on commit.

5. **Verify setup**
   ```bash
   pytest -q
   mypy src/ tests/ examples/
   ```

### Quick reference

| Task              | Command |
|-------------------|---------|
| Run all tests     | `pytest` |
| Verbose tests     | `pytest -v` |
| Tests + coverage  | `pytest --cov=profilis --cov-report=term-missing` |
| Single test file  | `pytest tests/test_fastapi_ui.py` |
| Tests by keyword  | `pytest -k "test_metrics"` |
| Lint              | `ruff check src/ tests/` |
| Format            | `ruff format .` or `black .` |
| Type-check        | `mypy src/ tests/ examples/` |

## Test-driven development (TDD)

We use **test-first development** so that design is driven by behaviour and changes stay safe.

### The TDD cycle

1. **Red** — Write a failing test that defines the desired behaviour (e.g. a new function, edge case, or fix). Run `pytest` and confirm the test fails for the right reason.
2. **Green** — Write the smallest amount of code that makes the test pass. Avoid adding behaviour the test doesn’t ask for.
3. **Refactor** — Improve names, structure, and performance while keeping all tests green. Re-run the suite after refactors.

Repeat this cycle in small steps so you always have a clear, failing test before writing production code.

### Running tests as you work

- **Full suite**: `pytest` or `pytest -q`
- **Current file**: `pytest path/to/test_file.py`
- **Single test**: `pytest path/to/test_file.py::test_function_name`
- **By pattern**: `pytest -k "adapter or middleware"`

Run tests often (e.g. after each Red/Green/Refactor step) so feedback is fast.

### Test layout

- Tests live under **`tests/`**.
- Mirror the source layout where it helps: e.g. `tests/test_fastapi_ui.py` for FastAPI UI, `tests/test_asgi_middleware.py` for ASGI middleware.
- Use **pytest fixtures** for shared setup (collectors, emitters, app instances). See existing tests for patterns.
- **Async tests**: use `async def test_...`; pytest-asyncio is enabled in `pyproject.toml` (`asyncio_mode = "auto"`).

### What to test

- **New behaviour**: Add tests that describe the public behaviour (inputs, outputs, side effects). Prefer testing through the public API.
- **Bug fixes**: Add a test that fails with the bug and passes after the fix (regression test).
- **Refactors**: Keep or adjust existing tests so they still pass; add tests only if you’re also changing behaviour.

### Example TDD flow

1. You want a helper that normalises route paths. **Red**: add `tests/test_utils.py` with `def test_normalise_route_strips_trailing_slash(): ...` and run `pytest tests/test_utils.py` — it fails (e.g. missing module or assertion).
2. **Green**: Implement the helper in `src/profilis/...` and import it in the test; run `pytest` until the test passes.
3. **Refactor**: Rename or simplify the implementation; run `pytest` again to confirm nothing breaks.

## Code quality

- **Linting**: `ruff check src/ tests/` (and fix or acknowledge any issues).
- **Formatting**: `ruff format .` or `black .` before committing.
- **Types**: `mypy src/ tests/ examples/` must pass (see `pyproject.toml` for config).
- **Pre-commit**: With `pre-commit install`, these run automatically on `git commit`. Run `pre-commit run --all-files` manually if needed.

## Pull requests

- **Branch**: Use a short-lived branch from main (`feat/...`, `fix/...`, `perf/...`, `chore/...`).
- **Scope**: Prefer small, focused PRs.
- **Requirements**: All tests pass; ruff and mypy pass; new behaviour or fixes have tests; user-facing changes have doc updates.
- **Commits**: Follow [Conventional Commits](https://www.conventionalcommits.org/) (e.g. `feat(adapters): add route exclusion for Sanic`).

## Related

- [Contributing](../meta/contributing.md) — How to contribute and what we expect
- [Architecture](../architecture/architecture.md) — System design and components
