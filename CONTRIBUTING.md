# Contributing to RowGuard

Thanks for contributing. The full guide lives in
[`docs/developer/CONTRIBUTING.md`](docs/developer/CONTRIBUTING.md)
([Read the Docs](https://rowguard.readthedocs.io/en/latest/developer/CONTRIBUTING.html)).

## Quick setup

```bash
git clone https://github.com/eddiethedean/rowguard.git
cd rowguard
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
python -m pip install -U pip
make install                # installs .[dev,async,sqlmodel] — matches CI
make all                    # ruff + mypy + pytest --cov
```

## Before you open a PR

1. Prefer small, focused changes on the **shipped** 0.5 surface (Core, async,
   streaming, ORM/SQLModel). See
   [Supported vs planned](docs/project/supported.md).
2. Do not implement deferred milestones (callbacks, plugins, reflection, raw
   SQL helpers) unless an issue explicitly asks for that work.
3. Run `make all` and keep examples/docs in sync when you change public APIs.
4. Use the bug / feature issue templates under `.github/ISSUE_TEMPLATE/`.

## Reporting security issues

Do **not** file a public issue. Follow [SECURITY.md](SECURITY.md).
