# Documentation

Sphinx site published at **[rowguard.readthedocs.io](https://rowguard.readthedocs.io/en/latest/)**.

| Audience | Entry |
| --- | --- |
| New users | [Start here](https://rowguard.readthedocs.io/en/latest/guides/start-here.html) · [Quickstart](https://rowguard.readthedocs.io/en/latest/guides/quickstart.html) |
| Async / streaming | [Async](https://rowguard.readthedocs.io/en/latest/guides/async.html) · [Streaming](https://rowguard.readthedocs.io/en/latest/guides/streaming.html) |
| Rejection policies | [Guide](https://rowguard.readthedocs.io/en/latest/guides/rejection-policies.html) |
| API | [API guide](https://rowguard.readthedocs.io/en/latest/api.html) · [Autodoc](https://rowguard.readthedocs.io/en/latest/reference/api.html) |
| Architecture | [Overview](https://rowguard.readthedocs.io/en/latest/architecture_overview.html) |

## Build locally

```bash
pip install -e ".[docs]"
make docs
```

Output: `docs/_build/html/index.html`. Uses Sphinx `-W` (warnings are errors),
matching CI and Read the Docs.

## Source layout

- `guides/` — tutorials and how-tos
- `reference/` — autodoc API pages
- `architecture/`, `validation/`, `rejection/`, `integrations/` — design notes
- `project/` — changelog / roadmap wrappers
- Root wrappers (`api.md`, `spec.md`, …) `{include}` canonical markdown from the repo root

Publishing: [READTHEDOCS.md](READTHEDOCS.md) · [`.readthedocs.yaml`](../.readthedocs.yaml)

## Single-source policy

Edit canonical files at the **repository root** (`API.md`, `SPEC.md`, …) or under
`docs/architecture/` etc. Do not duplicate content into thin wrappers.

| Edit this | Wrapper (do not duplicate) |
| --- | --- |
| `../API.md` | `api.md` |
| `../SPEC.md` | `spec.md` |
| `../ARCHITECTURE.md` | `architecture_overview.md` |
| `../README.md` | `readme.md` |
| `../CHANGELOG.md` | `project/changelog.md` |
| `../ROADMAP.md` | `project/roadmap.md` |

Standalone pages (edit directly): `guides/*`, `reference/api.md`, `index.md`.
