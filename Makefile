.PHONY: install test lint format type benchmark docs all

install:
	python -m pip install -e ".[dev,async,sqlmodel]"

test:
	pytest --cov=rowguard --cov-report=term-missing

lint:
	ruff check .

format:
	ruff format .

type:
	mypy src/rowguard tests/typing

benchmark:
	pytest benchmarks --benchmark-only

docs:
	python -m sphinx -b html -W docs docs/_build/html

all: lint type test
