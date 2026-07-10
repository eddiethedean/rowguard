# Releasing

How maintainers cut a RowGuard release.

## Checklist

1. Ensure `main` is green (CI: tests, docs, examples).
2. Update version in:
   - `pyproject.toml` (`project.version`)
   - `src/rowguard/__init__.py` (`__version__`)
   - `docs/conf.py` (`release` / `version`)
3. Update `CHANGELOG.md` (Keep a Changelog; add compare link).
4. Update `docs/project/supported.md` if the shipped surface changed.
5. Commit on `main` (or merge the release PR).
6. Tag and push:

```bash
git tag -a v0.4.0 -m "v0.4.0"
git push origin v0.4.0
```

7. GitHub Actions (`.github/workflows/release.yml`) builds and publishes to PyPI
   when a `v*` tag is pushed (requires `PYPI_API_TOKEN` secret).
8. Confirm the docs build on Read the Docs for the new tag/version.
9. Spot-check PyPI: `pip install rowguard==…`

## Versioning

RowGuard follows Semantic Versioning. Before 1.0, minor versions may include
breaking changes; document them clearly in the changelog.

## Related

- [Changelog](https://rowguard.readthedocs.io/en/latest/project/changelog.html)
- [Supported vs planned](https://rowguard.readthedocs.io/en/latest/project/supported.html)
