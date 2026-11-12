.DEFAULT_GOAL := ci

.PHONY: setup install-hooks update-hooks test lint typecheck format build ci

setup:
	uv sync --all-groups
	@$(MAKE) --no-print-directory install-hooks

install-hooks: ## (Re)install pre-commit hooks (repairs a stale interpreter path)
	@# `pre-commit install` bakes an absolute interpreter path into .git/hooks.
	@# A hook written against a different environment name, or against a worktree
	@# that has since been deleted, keeps failing until it is rewritten — and a
	@# "skip if the file exists" guard never rewrites it. Rewriting costs ~0.2s,
	@# so do it every time this repo owns its hooks directory.
	@if [ -f .git ]; then \
	  echo "hooks: worktree checkout — the canonical repo owns them, skipping"; \
	elif [ -n "$$(git config --get core.hooksPath 2>/dev/null)" ]; then \
	  echo "hooks: core.hooksPath is set — leaving it alone, skipping"; \
	else \
	  uv run pre-commit install --hook-type pre-commit --hook-type commit-msg; \
	fi

update-hooks: ## Bump hooks to their latest releases, frozen to commit SHAs
	uv run pre-commit autoupdate --freeze

test:
	uv run pytest --cov

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
