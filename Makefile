.DEFAULT_GOAL := ci

.PHONY: setup test lint typecheck format build ci

setup:
	UV_PROJECT_ENVIRONMENT=.venv uv sync --all-groups

test:
	UV_PROJECT_ENVIRONMENT=.venv uv run pytest

lint:
	UV_PROJECT_ENVIRONMENT=.venv uv run ruff check .

typecheck:
	UV_PROJECT_ENVIRONMENT=.venv uv run basedpyright

format:
	UV_PROJECT_ENVIRONMENT=.venv uv run ruff format .

build:
	UV_PROJECT_ENVIRONMENT=.venv uv build

ci: lint typecheck test build
	UV_PROJECT_ENVIRONMENT=.venv docgraph check --strict
