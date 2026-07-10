# Installation

## From PyPI

```bash
pip install rowguard
```

Async extras (aiosqlite + greenlet):

```bash
pip install "rowguard[async]"
```

## From source

```bash
git clone https://github.com/eddiethedean/rowguard.git
cd rowguard
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,async]"
```

## Verify

```python
import rowguard

print(rowguard.__version__)
```

## Documentation tooling

```bash
pip install -e ".[docs]"
make docs
```

Opens at `docs/_build/html/index.html`.

## Next

Continue with the [quickstart](quickstart.md).
