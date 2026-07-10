# Documentation build

This tree is the Sphinx source for [Read the Docs](https://rowguard.readthedocs.io).

## Local build

```bash
pip install -e ".[docs]"
make docs
open docs/_build/html/index.html
```

## Read the Docs project setup

1. Sign in at https://readthedocs.org/ with GitHub.
2. **Import a Project** → select `eddiethedean/rowguard`.
3. Confirm the project slug is `rowguard` (URL: `https://rowguard.readthedocs.io`).
4. Ensure **Build pull requests** is enabled if you want PR previews.
5. Trigger a build from the **Versions** / **Builds** tab (or push to `main`).

Configuration is entirely in the repo:

- [`.readthedocs.yaml`](../.readthedocs.yaml) — OS, Python, Sphinx path, install
- [`conf.py`](conf.py) — Sphinx + MyST settings
- [`requirements.txt`](requirements.txt) — Sphinx build dependencies

Root guides (`README.md`, `API.md`, …) are included via thin wrappers in this
directory so the markdown sources stay at the repository root.
