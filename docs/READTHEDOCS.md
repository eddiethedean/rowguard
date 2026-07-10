# Publishing on Read the Docs

This repository includes a [Sphinx](https://www.sphinx-doc.org/) site under `docs/`
using the **[Furo](https://pradyunsg.me/furo/)** theme (light/dark mode) with
MyST Markdown, sphinx-design cards, and copy buttons on code blocks.

## Connect Read the Docs

1. Sign in at [readthedocs.org](https://readthedocs.org/) with your GitHub account.
2. **Import a project** → select `eddiethedean/rowguard` (or your fork).
3. Keep the project slug as **`rowguard`** → `https://rowguard.readthedocs.io`.
4. RTD should detect [`.readthedocs.yaml`](../.readthedocs.yaml) automatically.
5. Set the default branch to `main`, save, and trigger a build.

| Setting | Value |
| --- | --- |
| Config file | `.readthedocs.yaml` |
| Sphinx config | `docs/conf.py` |
| Python requirements | `docs/requirements.txt` |
| Warnings | `fail_on_warning: true` |

## Local preview

```bash
pip install -e ".[docs]"
make docs
open docs/_build/html/index.html
```

## CI

GitHub Actions runs `make docs` in the **docs** job (`.github/workflows/ci.yml`).
Read the Docs publishes the same Sphinx configuration.

## Editing docs

| Audience | Path |
| --- | --- |
| Getting started / guides | `docs/guides/` |
| Autodoc API | `docs/reference/api.md` |
| Root guides included via wrappers | `API.md`, `SPEC.md`, … → `docs/api.md`, … |
| Deep design notes | `docs/architecture/`, `docs/validation/`, … |

Update `docs/index.md` toctrees when adding pages. Keep `{{ release }}` in the
home hero in sync via `myst_substitutions` in `conf.py`.
