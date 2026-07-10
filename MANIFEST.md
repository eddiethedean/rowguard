# Bundle Manifest

Included files for RowGuard **0.5.0**:

- `.github/workflows/benchmarks.yml`
- `.github/workflows/ci.yml`
- `.github/workflows/release.yml`
- `.gitignore`
- `.pre-commit-config.yaml`
- `.readthedocs.yaml`
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
- `SECURITY.md`
- `CODE_OF_CONDUCT.md`
- `RELEASING.md`
- `docs/` (Sphinx + Furo + MyST: `conf.py`, `index.md`, `guides/`, `examples/`,
  `reference/`, `project/`, architecture, developer, integrations, rejection,
  validation)

- `examples/basic.py`
- `examples/streaming.py`
- `examples/async_basic.py`
- `examples/orm_projected.py`
- `examples/orm_entity.py`
- `examples/sqlmodel_basic.py`
- `pyproject.toml`
- `src/rowguard/` including:
  - `api.py`, `cache.py`, `diagnostics.py`, `errors.py`, `statistics.py`
  - `adapters/` (sqlalchemy_row, orm_entity)
  - `execution/` (async_, context, observer, processor, state, sync, streaming)
  - `integrations/` (core, sqlrules, sqlalchemy_orm, sqlmodel)
  - `planning/` (compiler, config, execution_plan, request)
  - `plugins/`, `rejection/`, `results/` (query_result, rejected_row,
    stream_result, async_stream_result), `validation/`
- `tests/conftest.py`
- `tests/async/` (aselect, astream, parity, cancellation, edges)
- `tests/integration/test_core.py`
- `tests/integration/orm/`
- `tests/integration/sqlmodel/`
- `tests/streaming/` (stream, memory, edges)
- `tests/typing/` (query_result, stream_result, async_stream_result)
- `tests/unit/` (planner, planning_02, processor, policies, result, validator,
  adapter, orm_adapter, coverage edges, bugfix regressions, bugfix_02)
