# Documentation

Prefer **[Read the Docs](https://rowguard.readthedocs.io/en/latest/)** over
browsing these files on GitHub (MyST includes and toctrees render there).

If you are browsing the repo: open **`guides/`** first
([start-here.md](guides/start-here.md) → [quickstart.md](guides/quickstart.md)).
Folders such as `architecture/`, `rejection/`, and `validation/` are mostly
**design notes**—many describe unshipped work even when prose is present-tense.

| Audience | Entry |
| --- | --- |
| New users | [Start here](https://rowguard.readthedocs.io/en/latest/guides/start-here.html) |
| Scope | [Supported vs planned](https://rowguard.readthedocs.io/en/latest/project/supported.html) |
| Upgrade | [Upgrading](https://rowguard.readthedocs.io/en/latest/guides/upgrading.html) |
| Performance | [Performance](https://rowguard.readthedocs.io/en/latest/guides/performance.html) |
| API | [API guide](https://rowguard.readthedocs.io/en/latest/api.html) · [Errors](https://rowguard.readthedocs.io/en/latest/reference/errors.html) |
| Examples | [Examples](https://rowguard.readthedocs.io/en/latest/examples/index.html) |

## Build locally

```bash
pip install -e ".[docs]"
make docs
```

Output: `docs/_build/html/index.html`. Uses Sphinx `-W` (warnings are errors).

## Source layout

- `guides/` — tutorials and how-tos (start here)
- `examples/` — gallery pages
- `reference/` — autodoc + error catalog
- `architecture/`, `validation/`, `rejection/`, `integrations/` — design notes
- `project/` — changelog, roadmap, supported, security, releasing

Publishing: [READTHEDOCS.md](READTHEDOCS.md) · [`.readthedocs.yaml`](../.readthedocs.yaml)
