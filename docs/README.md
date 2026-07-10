# Documentation

Sphinx site published at **[rowguard.readthedocs.io](https://rowguard.readthedocs.io/en/latest/)**.

| Audience | Entry |
| --- | --- |
| New users | [Start here](https://rowguard.readthedocs.io/en/latest/guides/start-here.html) · [Quickstart](https://rowguard.readthedocs.io/en/latest/guides/quickstart.html) |
| Scope | [Supported vs planned](https://rowguard.readthedocs.io/en/latest/project/supported.html) |
| Async / streaming | [Async](https://rowguard.readthedocs.io/en/latest/guides/async.html) · [Streaming](https://rowguard.readthedocs.io/en/latest/guides/streaming.html) |
| API | [API guide](https://rowguard.readthedocs.io/en/latest/api.html) · [Autodoc](https://rowguard.readthedocs.io/en/latest/reference/api.html) |
| Examples | [Examples](https://rowguard.readthedocs.io/en/latest/examples/index.html) |

## Build locally

```bash
pip install -e ".[docs]"
make docs
```

Output: `docs/_build/html/index.html`. Uses Sphinx `-W` (warnings are errors).

## Source layout

- `guides/` — tutorials and how-tos
- `examples/` — gallery pages
- `reference/` — autodoc + error catalog
- `architecture/`, `validation/`, `rejection/`, `integrations/` — design notes (many deferred—see banners)
- `project/` — changelog, roadmap, supported, security, releasing

Publishing: [READTHEDOCS.md](READTHEDOCS.md) · [`.readthedocs.yaml`](../.readthedocs.yaml)
