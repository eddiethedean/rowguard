.PHONY: install test lint format type benchmark all

install:
	python -m pip install -e ".[dev,async]"

test:
	pytest --cov=rowguard --cov-report=term-missing

lint:
	ruff check .

format:
	ruff format .

type:
	mypy src/rowguard

benchmark:
	pytest benchmarks --benchmark-only

all: lint type test
