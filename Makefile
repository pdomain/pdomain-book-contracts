.DEFAULT_GOAL := ci

.PHONY: setup test lint typecheck format build ci

setup:
	uv sync --all-groups

test:
	uv run pytest

lint:
	uv run ruff check .

typecheck:
	uv run basedpyright

format:
	uv run ruff format .

build:
	uv build

ci: lint typecheck test build
	docgraph check --strict
