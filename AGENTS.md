# AGENTS — pdomain-book-contracts

Codex and other AI coding assistants: read [`CLAUDE.md`](CLAUDE.md),
[`CODEX.md`](CODEX.md), [`CONVENTIONS.md`](CONVENTIONS.md), and
[`DOCGRAPH.md`](DOCGRAPH.md) in this directory for docgraph-specific and
tool-specific context. This file is the canonical agent-guidance entry point.

Pure-Python contracts shared across the pdomain-* OCR suite: value types,
typography and matching algorithms, OCR result types, layout contracts, and
the PGDP round readers. Dependencies are limited to pydantic, pydantic-core,
shapely, and regex — no imaging or ML stack. `pdomain-book-tools` depends on
this package and re-exports its names.

Status: empty skeleton. The subpackages carry placeholder docstrings naming
what they will own; the code that fills them moves from `pdomain-book-tools`
in a later task of the `pdomain-ops` extraction plan, tracked in that
repository at
`docs/plans/2026-09-01-extract-book-contracts-and-retire-pd-repos.md` (not a
path in this repository).

- Python package: `pdomain_book_contracts/`.
- Tests: `tests/`; documentation: `docs/`.
- No imaging or ML dependency may enter this package. See
  `tests/test_torch_free_import.py`.
- `make test` runs the test suite.
- `make lint` runs Ruff.
- `make typecheck` runs basedpyright in strict mode.
- `make build` builds the package.
- `make ci` runs the full repository gate (lint, typecheck, test, build,
  `docgraph check --strict`).
- Use `uv run` for Python tools and scripts.
- Route new durable reader-facing documents through `writing-docs:write-readably`.
- Route edits of existing prose through `writing-docs:edit-for-readability`.
- Follow the consuming plugin's adversarial-review policy.
- Python changes follow the `writing-python:writing-python` mandatory gate.
