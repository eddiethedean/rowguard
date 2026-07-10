# Bundle Manifest

Included files for RowGuard **0.4.0**:

- `.github/workflows/benchmarks.yml`
- `.github/workflows/ci.yml`
- `.github/workflows/release.yml`
- `.gitignore`
- `.pre-commit-config.yaml`
- `API.md`
- `ARCHITECTURE.md`
- `CHANGELOG.md`
- `CURSOR_PROMPT.md`
- `LICENSE`
- `Makefile`
- `README.md`
- `ROADMAP.md`
- `SPEC.md`
- `benchmarks/conftest.py`
- `benchmarks/test_validation_benchmark.py`
- `docs/` (architecture, developer, integrations, rejection, validation)
- `examples/basic.py`
- `examples/streaming.py`
- `examples/async_basic.py`
- `pyproject.toml`
- `src/rowguard/` including:
  - `api.py`, `cache.py`, `diagnostics.py`, `errors.py`, `statistics.py`
  - `adapters/`, `execution/` (async_, context, observer, processor, state,
    sync, streaming)
  - `integrations/` (core, sqlrules; ORM/SQLModel stubs for 0.5.0)
  - `planning/` (compiler, config, execution_plan, request)
  - `plugins/`, `rejection/`, `results/` (query_result, rejected_row,
    stream_result, async_stream_result), `validation/`
- `tests/conftest.py`
- `tests/async/` (aselect, astream, parity, cancellation, edges)
- `tests/integration/test_core.py`
- `tests/streaming/` (stream, memory, edges)
- `tests/typing/` (query_result, stream_result, async_stream_result)
- `tests/unit/` (planner, planning_02, processor, policies, result, validator,
  adapter, coverage edges, bugfix regressions, bugfix_02)
