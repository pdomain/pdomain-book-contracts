# AGENTS — pdomain-book-contracts

## Agent Index

- **Kind:** process
- **Status:** active
- **Owner:** CT
- **Created:** 2026-09-02
- **Last verified:** 2026-11-06
- **Read when:** starting work in this repository.
- **Search terms:** agents, book contracts, dependency boundary, coverage.

`pdomain-book-contracts` is pure-Python contracts shared across the pdomain-*
OCR suite. Those contracts are value types, typography and matching
algorithms, OCR result types, layout contracts, annotation vocabularies, and
the PGDP round readers.

Runtime dependencies are pydantic, pydantic-core, shapely, regex, and
typing-extensions. There is no imaging or machine-learning stack.
`pdomain-book-tools` depends on this package and re-exports its names.

The package holds those contracts. The layout is in
[`docs/architecture/00-overview.md`](docs/architecture/00-overview.md).

Remaining work is the open coverage issue in
[`docs/issues/README.md`](docs/issues/README.md).

This file is the canonical agent-guidance entry point.

Codex and other AI coding assistants: read [`CLAUDE.md`](CLAUDE.md),
[`CODEX.md`](CODEX.md), [`CONVENTIONS.md`](CONVENTIONS.md), and
[`DOCGRAPH.md`](DOCGRAPH.md) in this directory for docgraph-specific and
tool-specific context.

- Python package: `pdomain_book_contracts/`.
- Tests: `tests/`.
- Documentation: `docs/`.
- No imaging or machine-learning dependency may enter this package. See
  `tests/test_torch_free_import.py`.
- `make test` runs the test suite.
- `make lint` runs Ruff.
- `make typecheck` runs basedpyright in strict mode.
- `make build` builds the package.
- `make ci` runs the full repository gate: lint, typecheck, test, build, and
  `docgraph check --strict`.
- Use `uv run` for Python tools and scripts.
- Route new durable reader-facing documents through `writing-docs:write-readably`.
- Route edits of existing prose through `writing-docs:edit-for-readability`.
- Follow the consuming plugin's adversarial-review policy.
- Python changes follow the `writing-python:writing-python` mandatory gate.
